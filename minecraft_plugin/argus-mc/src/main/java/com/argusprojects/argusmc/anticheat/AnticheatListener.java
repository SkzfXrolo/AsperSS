package com.argusprojects.argusmc.anticheat;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.PlayerDeathEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerItemConsumeEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerMoveEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerToggleSneakEvent;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.potion.PotionEffectType;
import org.bukkit.scheduler.BukkitTask;
import org.bukkit.util.Vector;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Bundle de checks anti-cheat implementados como handlers de eventos Bukkit.
 *
 * <p>Diseño: una sola clase Listener para reducir overhead de registro y
 * permitir compartir <code>PlayerState</code> entre checks (ej: el track de
 * "ticks en aire" es compartido por Fly y NoFall). Cada check vive en su
 * propio metodo privado <code>check{Nombre}(...)</code> para que sea facil
 * encontrarlos y desactivarlos.
 *
 * <p>Todos los checks consultan {@link AnticheatConfig#isCheckEnabled(String)}
 * antes de hacer trabajo, asi que desactivar uno desde config.yml es
 * gratuito (no recompilar).
 *
 * <p>Para mejorar precision en el futuro:
 *  - Migrar a ProtocolLib para inspeccion de packets reales (latencia 0).
 *  - Implementar movement prediction estilo GrimAC para reducir falsos
 *    positivos por TPS bajo o lag spikes.
 */
public final class AnticheatListener implements Listener {

    private final ArgusPlugin plugin;
    private final ViolationManager mgr;
    private final AnticheatConfig cfg;

    /** Estado por jugador. Limpiado al PlayerQuit. */
    private final Map<UUID, PlayerState> states = new HashMap<>();

    /** Tarea repetitiva (1 Hz) para checks que necesitan polling: Fly, Jesus. */
    private final BukkitTask repeatingTask;

    public AnticheatListener(ArgusPlugin plugin, ViolationManager mgr) {
        this.plugin = plugin;
        this.mgr    = mgr;
        this.cfg    = plugin.getAnticheatConfig();
        this.repeatingTask = plugin.getServer().getScheduler().runTaskTimer(
            plugin, this::tick, 20L, 20L); // cada segundo
    }

    /** Llamado en onDisable via HandlerList.unregisterAll. */
    public void shutdown() {
        if (repeatingTask != null) repeatingTask.cancel();
    }

    private PlayerState state(Player p) {
        return states.computeIfAbsent(p.getUniqueId(), k -> new PlayerState());
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Lifecycle
    // ─────────────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        states.put(p.getUniqueId(), new PlayerState());
        // Si tenia un SS forzado pendiente (HIGH violation antes de desconectar)
        if (mgr.hasPendingForcedSs(p.getUniqueId())) {
            mgr.consumePendingForcedSs(p);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        states.remove(e.getPlayer().getUniqueId());
        mgr.onPlayerQuit(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(PlayerDeathEvent e) {
        // reset de estado al morir (caida/lava/etc no debe contar como NoFall)
        Player p = e.getEntity();
        PlayerState s = state(p);
        s.airTicks = 0;
        s.lastFallDistance = 0f;
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Combat — Reach + KillauraAngle + AutoClicker
    // ─────────────────────────────────────────────────────────────────────

    @EventHandler(ignoreCancelled = true, priority = EventPriority.MONITOR)
    public void onAttack(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player attacker)) return;
        if (attacker.getGameMode() == GameMode.CREATIVE
            || attacker.getGameMode() == GameMode.SPECTATOR) return;
        if (attacker.hasPermission("argus.ac.bypass")) return;

        Entity target = e.getEntity();
        PlayerState s = state(attacker);
        long now = System.currentTimeMillis();

        // 1) Reach
        if (cfg.isCheckEnabled("reach")) {
            ConfigurationSection sec = cfg.checkSection("reach");
            double maxDist = sec != null ? sec.getDouble("max_distance", 4.5) : 4.5;
            double dist = attacker.getLocation().distance(target.getLocation());
            if (dist > maxDist) {
                ViolationLevel lvl;
                if (dist > maxDist + 2.5)      lvl = ViolationLevel.CRITICAL;
                else if (dist > maxDist + 1.0) lvl = ViolationLevel.HIGH;
                else if (dist > maxDist + 0.5) lvl = ViolationLevel.MID;
                else                            lvl = ViolationLevel.LOW;
                mgr.flag(new Violation(attacker, "reach", lvl,
                    String.format("dist=%.2fb (max=%.2fb)", dist, maxDist)));
            }
        }

        // 2) Killaura — angulo entre vector de mirada y vector hacia el target
        if (cfg.isCheckEnabled("killaura_angle")) {
            ConfigurationSection sec = cfg.checkSection("killaura_angle");
            double maxAngle = sec != null ? sec.getDouble("max_angle_deg", 60.0) : 60.0;
            Vector lookDir = attacker.getEyeLocation().getDirection().normalize();
            Vector toTarget = target.getLocation().toVector()
                .subtract(attacker.getEyeLocation().toVector());
            if (toTarget.lengthSquared() > 0.0001) {
                toTarget.normalize();
                double dot = Math.max(-1.0, Math.min(1.0, lookDir.dot(toTarget)));
                double angle = Math.toDegrees(Math.acos(dot));
                if (angle > maxAngle) {
                    ViolationLevel lvl = (angle > 110) ? ViolationLevel.HIGH
                                       : (angle > 85)  ? ViolationLevel.MID
                                                       : ViolationLevel.LOW;
                    mgr.flag(new Violation(attacker, "killaura_angle", lvl,
                        String.format("angulo=%.0fdeg (max=%.0fdeg)", angle, maxAngle)));
                }
            }
        }

        // 3) Auto-clicker — CPS sostenidos
        if (cfg.isCheckEnabled("autoclicker")) {
            ConfigurationSection sec = cfg.checkSection("autoclicker");
            int maxCps = sec != null ? sec.getInt("max_cps", 20) : 20;
            s.attackTimes.addLast(now);
            // Limpiar > 1 segundo de antiguedad
            while (!s.attackTimes.isEmpty() && now - s.attackTimes.peekFirst() > 1000L) {
                s.attackTimes.pollFirst();
            }
            int cps = s.attackTimes.size();
            if (cps > maxCps) {
                ViolationLevel lvl = cps > maxCps + 10 ? ViolationLevel.HIGH
                                   : cps > maxCps + 5  ? ViolationLevel.MID
                                                       : ViolationLevel.LOW;
                mgr.flag(new Violation(attacker, "autoclicker", lvl,
                    "cps=" + cps + " (max=" + maxCps + ")"));
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Movement — Fly, Speed, NoFall, Jesus, Scaffold
    // ─────────────────────────────────────────────────────────────────────

    @EventHandler(ignoreCancelled = true, priority = EventPriority.MONITOR)
    public void onMove(PlayerMoveEvent e) {
        Player p = e.getPlayer();
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return;
        if (p.hasPermission("argus.ac.bypass")) return;

        PlayerState s = state(p);
        Location from = e.getFrom();
        Location to   = e.getTo();
        if (to == null) return;

        // Distancia horizontal recorrida en este move (no usamos delta de Y)
        double dx = to.getX() - from.getX();
        double dz = to.getZ() - from.getZ();
        double horizSq = dx * dx + dz * dz;

        // Speed check
        if (cfg.isCheckEnabled("speed")) {
            ConfigurationSection sec = cfg.checkSection("speed");
            double maxBps = sec != null ? sec.getDouble("max_blocks_per_sec", 8.0) : 8.0;
            // Acumular distancia en la ventana de 1 segundo
            long now = System.currentTimeMillis();
            s.distSamples.addLast(new double[]{now, Math.sqrt(horizSq)});
            while (!s.distSamples.isEmpty() && now - (long)s.distSamples.peekFirst()[0] > 1000L) {
                s.distSamples.pollFirst();
            }
            double accum = 0;
            for (double[] sample : s.distSamples) accum += sample[1];
            // Permite excepciones: sprint+jump+ice = ~7.6 bps, elytra fly altisimo
            boolean elytra = p.isGliding();
            boolean speedPotion = p.hasPotionEffect(PotionEffectType.SPEED);
            double effectiveMax = maxBps + (speedPotion ? 4.0 : 0) + (elytra ? 30 : 0);
            if (accum > effectiveMax) {
                ViolationLevel lvl;
                if (accum > effectiveMax * 2.0)   lvl = ViolationLevel.HIGH;
                else if (accum > effectiveMax * 1.4) lvl = ViolationLevel.MID;
                else                              lvl = ViolationLevel.LOW;
                mgr.flag(new Violation(p, "speed", lvl,
                    String.format("%.1fbps (max=%.1f)", accum, effectiveMax)));
            }
        }

        // NoFall — track de fall distance
        if (p.getFallDistance() > s.lastFallDistance) {
            s.lastFallDistance = p.getFallDistance();
        }

        // Jesus check (caminar sobre agua sin sumergirse)
        if (cfg.isCheckEnabled("jesus")) {
            Block below = to.clone().add(0, -0.05, 0).getBlock();
            Block at    = to.getBlock();
            boolean liquidBelow = below.isLiquid();
            boolean inLiquid    = at.isLiquid();
            if (liquidBelow && !inLiquid && horizSq > 0.001) {
                // El jugador esta caminando POR ENCIMA del liquido
                if (!p.isGliding()
                    && p.getVehicle() == null
                    && !p.hasPotionEffect(PotionEffectType.WATER_BREATHING)) {
                    s.jesusTicks++;
                    if (s.jesusTicks > 5) {
                        mgr.flag(new Violation(p, "jesus", ViolationLevel.MID,
                            "caminando sobre liquido " + s.jesusTicks + " ticks"));
                        s.jesusTicks = 0;
                    }
                }
            } else {
                s.jesusTicks = 0;
            }
        }
    }

    /** Loop 1 Hz: Fly check (necesita ticks acumulados, no eventos). */
    private void tick() {
        if (cfg == null || !cfg.isEnabled()) return;
        for (Player p : plugin.getServer().getOnlinePlayers()) {
            if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) continue;
            if (p.hasPermission("argus.ac.bypass")) continue;
            if (p.getAllowFlight() || p.isFlying()) continue;
            if (p.isGliding()) continue;

            PlayerState s = state(p);
            boolean onGround = p.isOnGround();
            if (onGround) {
                s.airTicks = 0;
            } else {
                s.airTicks++;
                if (cfg.isCheckEnabled("fly")) {
                    ConfigurationSection sec = cfg.checkSection("fly");
                    int maxAir = sec != null ? sec.getInt("max_air_ticks", 60) : 60;
                    // Conversion: tick() corre cada 20 ticks (1s), asi que dividimos
                    // entre 20 para comparar con ticks reales del config.
                    if (s.airTicks * 20 > maxAir) {
                        // Si NO esta cayendo (velocidad Y >= 0) por mucho rato → fly
                        if (p.getVelocity().getY() >= -0.05) {
                            ViolationLevel lvl = s.airTicks > 10 ? ViolationLevel.CRITICAL
                                               : s.airTicks > 5  ? ViolationLevel.HIGH
                                                                 : ViolationLevel.MID;
                            mgr.flag(new Violation(p, "fly", lvl,
                                "en aire " + s.airTicks + "s sin caer (vy=" +
                                String.format("%.2f", p.getVelocity().getY()) + ")"));
                            s.airTicks = 0;
                        }
                    }
                }
            }
        }
    }

    @EventHandler(ignoreCancelled = true, priority = EventPriority.MONITOR)
    public void onDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PlayerState s = state(p);
        if (e.getCause() == EntityDamageEvent.DamageCause.FALL) {
            s.lastFallDistance = 0f;
        }
    }

    /** NoFall — si el jugador toca suelo y NO tomo daño tras una caida grande. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onLand(PlayerMoveEvent e) {
        // (handler separado para legibilidad, podriamos fusionarlo con onMove)
        if (!cfg.isCheckEnabled("nofall")) return;
        Player p = e.getPlayer();
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        if (p.getAllowFlight() || p.isGliding()) return;
        PlayerState s = state(p);
        if (p.isOnGround() && s.lastFallDistance > 4.0f) {
            // Cayo > 4 bloques pero damage no ocurrio (esperamos un par de ticks
            // por consistencia: si en el siguiente tick sigue >0, es NoFall).
            // Para evitar falsos positivos, solo flagamos si la caida fue realmente
            // grande (> 6 bloques).
            float fallDist = s.lastFallDistance;
            s.lastFallDistance = 0f;
            if (fallDist > 6.0f) {
                ViolationLevel lvl = fallDist > 15.0f ? ViolationLevel.HIGH
                                                       : ViolationLevel.MID;
                mgr.flag(new Violation(p, "nofall", lvl,
                    String.format("cayo %.1fb sin daño", fallDist)));
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Scaffold — colocar bloque mirando hacia abajo mientras se mueve
    // ─────────────────────────────────────────────────────────────────────

    @EventHandler(ignoreCancelled = true, priority = EventPriority.MONITOR)
    public void onPlace(BlockPlaceEvent e) {
        if (!cfg.isCheckEnabled("scaffold")) return;
        Player p = e.getPlayer();
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return;
        if (p.hasPermission("argus.ac.bypass")) return;

        // Pitch = angulo vertical de la mirada. > 60deg = mirando bastante abajo.
        // Si ademas se mueve horizontalmente y el bloque se coloca DEBAJO suyo,
        // es scaffold (estilo Towering / Bridging).
        float pitch = p.getLocation().getPitch();
        if (pitch < 50f) return;

        Block placed = e.getBlockPlaced();
        Location pl = p.getLocation();
        if (placed.getY() > pl.getY()) return; // bloque arriba: no es scaffold

        PlayerState s = state(p);
        long now = System.currentTimeMillis();
        s.scaffoldHits.addLast(now);
        while (!s.scaffoldHits.isEmpty() && now - s.scaffoldHits.peekFirst() > 3000L) {
            s.scaffoldHits.pollFirst();
        }
        if (s.scaffoldHits.size() >= 4) {
            // 4 placements en 3s mirando hacia abajo y debajo del player → scaffold
            ViolationLevel lvl = s.scaffoldHits.size() >= 8 ? ViolationLevel.HIGH
                                                            : ViolationLevel.MID;
            mgr.flag(new Violation(p, "scaffold", lvl,
                s.scaffoldHits.size() + " placements abajo en 3s, pitch=" + (int)pitch));
            s.scaffoldHits.clear();
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    //  FastEat
    // ─────────────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteract(PlayerInteractEvent e) {
        if (!cfg.isCheckEnabled("fasteat")) return;
        if (e.getItem() == null) return;
        Material mat = e.getItem().getType();
        if (!isEdible(mat)) return;
        // Cualquier interact con item comestible inicia el timer
        state(e.getPlayer()).eatStartedMs = System.currentTimeMillis();
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onConsume(PlayerItemConsumeEvent e) {
        if (!cfg.isCheckEnabled("fasteat")) return;
        Player p = e.getPlayer();
        PlayerState s = state(p);
        if (s.eatStartedMs <= 0) return;
        long elapsed = System.currentTimeMillis() - s.eatStartedMs;
        s.eatStartedMs = 0;
        ConfigurationSection sec = cfg.checkSection("fasteat");
        long min = sec != null ? sec.getLong("min_eat_ms", 1400L) : 1400L;
        if (elapsed < min) {
            ViolationLevel lvl = elapsed < min / 2 ? ViolationLevel.HIGH
                                                   : ViolationLevel.MID;
            mgr.flag(new Violation(p, "fasteat", lvl,
                "comio " + e.getItem().getType().name() + " en " + elapsed + "ms"));
        }
    }

    private static boolean isEdible(Material m) {
        return m.isEdible();
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Chat & command spam
    // ─────────────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onChat(AsyncPlayerChatEvent e) {
        if (!cfg.isCheckEnabled("chat_spam")) return;
        Player p = e.getPlayer();
        if (p.hasPermission("argus.ac.bypass")) return;
        PlayerState s = state(p);
        long now = System.currentTimeMillis();
        s.chatTimes.addLast(now);
        while (!s.chatTimes.isEmpty() && now - s.chatTimes.peekFirst() > 5000L) {
            s.chatTimes.pollFirst();
        }
        ConfigurationSection sec = cfg.checkSection("chat_spam");
        int max = sec != null ? sec.getInt("max_msgs_per_5s", 5) : 5;
        if (s.chatTimes.size() > max) {
            ViolationLevel lvl = s.chatTimes.size() > max * 2 ? ViolationLevel.MID
                                                              : ViolationLevel.LOW;
            mgr.flag(new Violation(p, "chat_spam", lvl,
                s.chatTimes.size() + " msgs/5s (max=" + max + ")"));
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onCmd(PlayerCommandPreprocessEvent e) {
        if (!cfg.isCheckEnabled("cmd_spam")) return;
        Player p = e.getPlayer();
        if (p.hasPermission("argus.ac.bypass")) return;
        PlayerState s = state(p);
        long now = System.currentTimeMillis();
        s.cmdTimes.addLast(now);
        while (!s.cmdTimes.isEmpty() && now - s.cmdTimes.peekFirst() > 5000L) {
            s.cmdTimes.pollFirst();
        }
        ConfigurationSection sec = cfg.checkSection("cmd_spam");
        int max = sec != null ? sec.getInt("max_cmds_per_5s", 8) : 8;
        if (s.cmdTimes.size() > max) {
            ViolationLevel lvl = s.cmdTimes.size() > max * 2 ? ViolationLevel.MID
                                                             : ViolationLevel.LOW;
            mgr.flag(new Violation(p, "cmd_spam", lvl,
                s.cmdTimes.size() + " cmds/5s (max=" + max + ")"));
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Inventory move (mover items mientras camina rapido)
    // ─────────────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInvClick(InventoryClickEvent e) {
        if (!cfg.isCheckEnabled("inventory_move")) return;
        if (!(e.getWhoClicked() instanceof Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        if (e.getInventory().getHolder() != null && !(e.getInventory().getHolder() instanceof Player)) return;

        PlayerState s = state(p);
        // Si en la ultima ventana de 500ms se movió mucho, flag.
        long now = System.currentTimeMillis();
        double recentDist = 0;
        for (double[] sample : s.distSamples) {
            if (now - (long)sample[0] < 500L) recentDist += sample[1];
        }
        if (recentDist > 2.0) { // > 2 bloques en 500ms = sprinting
            mgr.flag(new Violation(p, "inventory_move", ViolationLevel.LOW,
                String.format("clicked inv mientras movia %.1fb/0.5s", recentDist)));
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSneak(PlayerToggleSneakEvent e) {
        // Hook reservado para futuros checks (ej: detectar AutoSneak).
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Estado por jugador
    // ─────────────────────────────────────────────────────────────────────

    private static final class PlayerState {
        // Combat
        final Deque<Long> attackTimes = new ArrayDeque<>();
        // Movement
        final Deque<double[]> distSamples = new ArrayDeque<>(); // [tsMs, distHoriz]
        int  airTicks = 0;
        float lastFallDistance = 0f;
        int  jesusTicks = 0;
        // Scaffold
        final Deque<Long> scaffoldHits = new ArrayDeque<>();
        // FastEat
        long eatStartedMs = 0;
        // Spam
        final Deque<Long> chatTimes = new ArrayDeque<>();
        final Deque<Long> cmdTimes  = new ArrayDeque<>();
    }
}
