package com.argusprojects.argusmc.anticheat;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.RayTraceResult;
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
import org.bukkit.event.player.PlayerAnimationEvent;
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

    /** Modo debug global: si esta ON, cada hit logea TODA la telemetria al
     *  staff con permiso 'argus.alerts'. Util para entender por que un cheat
     *  no esta siendo detectado. Toggle desde /argus debug. */
    public static volatile boolean debugMode = false;

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
        // Debug feedback: avisar por que se ignora un hit (creative/bypass).
        // Asi el staff no se queda preguntandose si el plugin esta vivo.
        if (attacker.getGameMode() == GameMode.CREATIVE
            || attacker.getGameMode() == GameMode.SPECTATOR) {
            if (debugMode) {
                debugBroadcast("&8[&6AC-DEBUG&8] &7" + attacker.getName()
                    + " hit ignorado: gamemode=" + attacker.getGameMode().name()
                    + " &8(usa /gamemode survival para activar AC)");
            }
            return;
        }
        if (attacker.hasPermission("argus.ac.bypass")) {
            if (debugMode) {
                debugBroadcast("&8[&6AC-DEBUG&8] &7" + attacker.getName()
                    + " hit ignorado: tiene permiso argus.ac.bypass");
            }
            return;
        }

        Entity target = e.getEntity();
        PlayerState s = state(attacker);
        long now = System.currentTimeMillis();

        // Skipear ataques contra item entities, area effect clouds, etc.
        // Esos no son hits "reales" y no deben gatillar checks de combate.
        org.bukkit.entity.EntityType tt = target.getType();
        if (tt == org.bukkit.entity.EntityType.ITEM
            || tt == org.bukkit.entity.EntityType.AREA_EFFECT_CLOUD
            || tt == org.bukkit.entity.EntityType.EXPERIENCE_ORB
            || tt == org.bukkit.entity.EntityType.LIGHTNING_BOLT) return;
        // Skipear self-attack (suicidio con bow al aire, etc.)
        if (target.getUniqueId().equals(attacker.getUniqueId())) return;

        // El damage puede venir indirectamente de un proyectil (arrow, trident,
        // snowball). En esos casos, EntityDamageByEntityEvent.getDamager() es
        // el ATTACKER pero el hit fisico no es un swing — ningun packet de
        // animation acompaña. Los checks de killaura no aplican aca.
        boolean isMeleeHit = (e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK
                           || e.getCause() == EntityDamageEvent.DamageCause.ENTITY_SWEEP_ATTACK);

        // 0) Killaura — sin swing previo. Cliente vainilla SIEMPRE envia
        // PlayerAnimationEvent (swing main hand) antes de un EntityDamage.
        // Si paso > 400ms desde el ultimo swing, es cheat killaura "silent".
        // Skipeamos:
        //   - El PRIMER hit del jugador en su sesion (lastSwingMs==0): puede
        //     que el AnimationEvent y el DamageEvent lleguen invertidos (orden
        //     de event dispatch no garantizado). 1 falso negativo es preferible
        //     a 1 falso positivo.
        //   - Hits que NO son melee directo (proyectiles, sweep collateral).
        //   - Sweep attack collateral: cuando un hit melee golpea varios
        //     mobs por el sweep enchant, solo el target principal tiene el
        //     swing asociado.
        if (cfg.isCheckEnabled("killaura_no_swing") && isMeleeHit && s.lastSwingMs > 0
            && e.getCause() != EntityDamageEvent.DamageCause.ENTITY_SWEEP_ATTACK) {
            ConfigurationSection sec = cfg.checkSection("killaura_no_swing");
            long maxAge = sec != null ? sec.getLong("max_swing_age_ms", 600L) : 600L;
            long swingAge = now - s.lastSwingMs;
            if (swingAge > maxAge) {
                ViolationLevel lvl = swingAge > 5000 ? ViolationLevel.HIGH
                                                     : ViolationLevel.MID;
                mgr.flag(new Violation(attacker, "killaura_no_swing", lvl,
                    "swing fue hace " + swingAge + "ms (max " + maxAge + "ms)"));
            }
        }

        // Telemetria debug — TODO hit logea metricas si /argus debug esta ON
        if (debugMode) {
            double dist = closestDistanceToEntity(attacker.getEyeLocation(), target);
            double angle = minAngleToHitbox(attacker.getEyeLocation(), target);
            long swingAge = s.lastSwingMs == 0 ? -1 : now - s.lastSwingMs;
            int cps = s.attackTimes.size();
            debugBroadcast(String.format(
                "&8[&6AC-DEBUG&8] &7%s -> %s &8| &7dist=&f%.2fb &7angle=&f%.0fdeg &7swing=&f%dms &7cps=&f%d &7yaw=&f%.0f",
                attacker.getName(), target.getType().name().toLowerCase(),
                dist, angle, swingAge, cps + 1, attacker.getLocation().getYaw()));
        }

        // 1) Reach — Solo aplica para melee, no para proyectiles.
        //    Default 4.5b (vainilla 1.8 PvP estandar es 3.0 survival pero 4.5
        //    es lo aceptado en la mayoria de servers). Compensacion de ping:
        //    100ms de ping = ~1.0 bloque de tolerancia extra (porque el target
        //    se movio en el intervalo entre client-side hit y server-side check).
        if (cfg.isCheckEnabled("reach") && isMeleeHit) {
            ConfigurationSection sec = cfg.checkSection("reach");
            double maxDist = sec != null ? sec.getDouble("max_distance", 4.5) : 4.5;
            double dist = closestDistanceToEntity(attacker.getEyeLocation(), target);
            // Compensacion de ping: hasta +1.5b extra para players con ping alto.
            double pingComp = 0;
            try {
                int ping = attacker.getPing();
                pingComp = Math.min(1.5, Math.max(0, ping / 100.0));
            } catch (Throwable ignored) {}
            double tolerance = maxDist + pingComp;
            if (dist > tolerance) {
                double over = dist - tolerance;
                ViolationLevel lvl;
                if (over > 2.5)       lvl = ViolationLevel.CRITICAL;
                else if (over > 1.5)  lvl = ViolationLevel.HIGH;
                else if (over > 0.7)  lvl = ViolationLevel.MID;
                else                  lvl = ViolationLevel.LOW;
                mgr.flag(new Violation(attacker, "reach", lvl,
                    String.format("dist=%.2fb (max=%.2fb +%.1fb ping)", dist, maxDist, pingComp)));
            }
        }

        // 2) Killaura por angulo — calculado contra TODA la hitbox.
        //    Solo aplica a hits melee (proyectiles no requieren mirar al target).
        //    Default 90deg: es FACIL girar 60-80deg en plena pelea PvP entre
        //    el momento del click y el server-side measurement. 90deg es el
        //    threshold donde realmente "no se puede haber visto el target".
        //    Solo flageamos si killaura_angle EN COMBINACION con killaura_no_swing
        //    o killaura_yaw_snap suman en ViolationManager — solo es señal LOW.
        if (cfg.isCheckEnabled("killaura_angle") && isMeleeHit) {
            ConfigurationSection sec = cfg.checkSection("killaura_angle");
            double maxAngle = sec != null ? sec.getDouble("max_angle_deg", 90.0) : 90.0;
            double angle = minAngleToHitbox(attacker.getEyeLocation(), target);
            if (angle > maxAngle) {
                ViolationLevel lvl = (angle > 150) ? ViolationLevel.HIGH
                                   : (angle > 120) ? ViolationLevel.MID
                                                   : ViolationLevel.LOW;
                mgr.flag(new Violation(attacker, "killaura_angle", lvl,
                    String.format("angulo=%.0fdeg (max=%.0fdeg)", angle, maxAngle)));
            }
        }

        // 3) Killaura — multi-target. Vape switchea entre N mobs en pocos ms
        //    para multi-hit. PERO la espada vainilla con Sweeping Edge enchant
        //    tambien golpea hasta 4 mobs adyacentes en un solo swing (sweep
        //    attack). Detectamos eso por el cause ENTITY_SWEEP_ATTACK y por
        //    si el item en mano es una sword con sweeping edge.
        //    Tampoco contamos hits con cause distinto a ENTITY_ATTACK
        //    (proyectiles, sweeps son diferentes events).
        if (cfg.isCheckEnabled("killaura_multi")
            && e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK
            && isHumanLikeTarget(target)) {
            ConfigurationSection sec = cfg.checkSection("killaura_multi");
            long windowMs = sec != null ? sec.getLong("window_ms", 250L) : 250L;
            int  minTargets = sec != null ? sec.getInt("min_distinct_targets", 4) : 4;
            UUID tid = target.getUniqueId();
            s.recentTargets.addLast(new long[]{now, tid.getMostSignificantBits(), tid.getLeastSignificantBits()});
            while (!s.recentTargets.isEmpty() && now - s.recentTargets.peekFirst()[0] > windowMs) {
                s.recentTargets.pollFirst();
            }
            java.util.HashSet<Long> uniq = new java.util.HashSet<>();
            for (long[] t : s.recentTargets) uniq.add(t[1] ^ (t[2] << 1));
            if (uniq.size() >= minTargets) {
                int n = uniq.size();
                ViolationLevel lvl = n >= 6 ? ViolationLevel.HIGH
                                   : n >= 5 ? ViolationLevel.MID
                                            : ViolationLevel.LOW;
                mgr.flag(new Violation(attacker, "killaura_multi", lvl,
                    n + " targets distintos en " + windowMs + "ms"));
            }
        }

        // 4) Killaura — yaw snap detection. Comparamos el yaw "estable"
        //    (ultimo MoveEvent) con el yaw AHORA. Si difiere mucho y hace
        //    muy poco, sospechoso de silent rotation.
        //
        //    PERO: girarse rapido a un enemigo en PvP es totalmente normal.
        //    Solo flageamos si el snap NO esta orientado HACIA el target (es
        //    decir, despues del snap el attacker mira en otra direccion que
        //    no es donde esta el target). Killaura cheats reales hacen snap
        //    PARA el hit y luego back, asi que medimos la direccion final.
        if (cfg.isCheckEnabled("killaura_yaw_snap") && isMeleeHit) {
            ConfigurationSection sec = cfg.checkSection("killaura_yaw_snap");
            double maxDelta = sec != null ? sec.getDouble("max_delta_deg", 130.0) : 130.0;
            long maxAgeMs   = sec != null ? sec.getLong("max_age_ms", 200L) : 200L;
            if (s.lastYawSampleMs > 0 && now - s.lastYawSampleMs <= maxAgeMs) {
                float currentYaw = attacker.getLocation().getYaw();
                double delta = Math.abs(yawDelta(s.lastMoveYaw, currentYaw));
                if (delta > maxDelta) {
                    // Calcular el yaw esperado HACIA el target.
                    double dxT = target.getLocation().getX() - attacker.getLocation().getX();
                    double dzT = target.getLocation().getZ() - attacker.getLocation().getZ();
                    float expectedYaw = (float) (Math.toDegrees(Math.atan2(-dxT, dzT)));
                    double misalign = Math.abs(yawDelta(currentYaw, expectedYaw));
                    // Si ahora SI esta mirando al target (misalign < 30deg), el snap
                    // fue legitimo (giro a por el enemigo). Solo flag si despues del
                    // snap NO esta mirando al target — eso es killaura silent.
                    if (misalign > 45) {
                        ViolationLevel lvl = delta > 160 ? ViolationLevel.HIGH
                                           : ViolationLevel.MID;
                        mgr.flag(new Violation(attacker, "killaura_yaw_snap", lvl,
                            String.format("yaw delta=%.0fdeg en %dms (misalign=%.0fdeg)",
                                delta, now - s.lastYawSampleMs, misalign)));
                    }
                }
            }
        }

        // 5) Hit through wall — ray-trace desde el ojo hacia el target.
        //    Solo aplica a melee. Whitelist amplia de bloques que NO son
        //    pared completa (transparentes, de altura parcial, etc.) — Bukkit
        //    los marca como solid pero se puede pegar a traves visualmente.
        if (cfg.isCheckEnabled("hit_through_wall") && isMeleeHit) {
            try {
                Vector to = target.getLocation().add(0, target.getHeight() / 2.0, 0)
                    .toVector().subtract(attacker.getEyeLocation().toVector());
                double dist = to.length();
                if (dist > 0.5 && dist < 8.0) {
                    Vector dir = to.clone().normalize();
                    RayTraceResult rt = attacker.getWorld().rayTraceBlocks(
                        attacker.getEyeLocation(), dir, dist - 0.3,
                        org.bukkit.FluidCollisionMode.NEVER, true);
                    if (rt != null && rt.getHitBlock() != null) {
                        Block hitBlock = rt.getHitBlock();
                        Material bm = hitBlock.getType();
                        String bn = bm.name();
                        boolean isPartial =
                            bn.contains("STAIRS") || bn.contains("SLAB") || bn.contains("FENCE")
                            || bn.contains("WALL") || bn.contains("GLASS") || bn.contains("BARS")
                            || bn.contains("DOOR") || bn.contains("TRAPDOOR") || bn.contains("CARPET")
                            || bn.contains("PANE") || bn.contains("CHAIN") || bn.contains("LANTERN")
                            || bn.contains("CANDLE") || bn.contains("AMETHYST") || bn.contains("LADDER")
                            || bn.contains("SCAFFOLDING") || bn.contains("SIGN") || bn.contains("BUTTON")
                            || bn.contains("PRESSURE_PLATE") || bn.contains("LEAVES");
                        if (bm.isSolid() && !hitBlock.isPassable() && !isPartial) {
                            double hitDist = rt.getHitPosition().distance(attacker.getEyeLocation().toVector());
                            if (hitDist < dist - 0.2) {
                                mgr.flag(new Violation(attacker, "hit_through_wall", ViolationLevel.HIGH,
                                    String.format("hit a %s a %.1fb a traves de %s",
                                        target.getType().name().toLowerCase(),
                                        dist, bn.toLowerCase())));
                            }
                        }
                    }
                }
            } catch (Exception ex) { /* ray-trace puede fallar en edge cases */ }
        }

        // 6) Auto-clicker — CPS + varianza de intervalos. Atrapa cheats humanizados.
        //    Solo aplica a melee. Subimos defaults: max_cps=22 (algunos jugadores
        //    butterfly clickers humanos llegan a 18-20). Variance pivot=12
        //    (no medir varianza si CPS<12, porque a CPS bajo cualquiera puede
        //    ser regular). min_stddev=25ms (humanos tipicos: 30-80ms stddev).
        if (cfg.isCheckEnabled("autoclicker") && isMeleeHit) {
            ConfigurationSection sec = cfg.checkSection("autoclicker");
            int maxCps = sec != null ? sec.getInt("max_cps", 22) : 22;
            int variancePivotCps = sec != null ? sec.getInt("variance_min_cps", 12) : 12;
            double minStdDevMs = sec != null ? sec.getDouble("min_stddev_ms", 25.0) : 25.0;
            int    minSamples  = sec != null ? sec.getInt("min_samples", 12) : 12;

            // Track del intervalo desde el ultimo hit
            if (s.lastAttackMs > 0) {
                s.attackIntervals.addLast(now - s.lastAttackMs);
                while (s.attackIntervals.size() > 30) s.attackIntervals.pollFirst();
            }
            s.lastAttackMs = now;

            // CPS clasico
            s.attackTimes.addLast(now);
            while (!s.attackTimes.isEmpty() && now - s.attackTimes.peekFirst() > 1000L) {
                s.attackTimes.pollFirst();
            }
            int cps = s.attackTimes.size();
            if (cps > maxCps) {
                ViolationLevel lvl = cps > maxCps + 12 ? ViolationLevel.HIGH
                                   : cps > maxCps + 6  ? ViolationLevel.MID
                                                       : ViolationLevel.LOW;
                mgr.flag(new Violation(attacker, "autoclicker", lvl,
                    "cps=" + cps + " (max=" + maxCps + ")"));
            }
            // Varianza: si el player clickea con stddev MUY bajo, es bot.
            //  Solo evaluamos si CPS alto Y muestras suficientes — y aun asi
            //  el level es solo LOW (señal contributoria, no decisiva).
            else if (cps >= variancePivotCps && s.attackIntervals.size() >= minSamples) {
                double mean = 0;
                for (long iv : s.attackIntervals) mean += iv;
                mean /= s.attackIntervals.size();
                double variance = 0;
                for (long iv : s.attackIntervals) variance += (iv - mean) * (iv - mean);
                variance /= s.attackIntervals.size();
                double stddev = Math.sqrt(variance);
                if (stddev < minStdDevMs) {
                    mgr.flag(new Violation(attacker, "autoclicker_variance", ViolationLevel.LOW,
                        String.format("cps=%d stddev=%.1fms (min=%.1fms)", cps, stddev, minStdDevMs)));
                }
            }
        }
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Helpers de combate
    // ─────────────────────────────────────────────────────────────────────

    /** Distancia desde un punto al borde mas cercano de la bounding box de la entidad. */
    private static double closestDistanceToEntity(Location origin, Entity target) {
        try {
            org.bukkit.util.BoundingBox bb = target.getBoundingBox();
            double cx = clamp(origin.getX(), bb.getMinX(), bb.getMaxX());
            double cy = clamp(origin.getY(), bb.getMinY(), bb.getMaxY());
            double cz = clamp(origin.getZ(), bb.getMinZ(), bb.getMaxZ());
            double dx = origin.getX() - cx;
            double dy = origin.getY() - cy;
            double dz = origin.getZ() - cz;
            return Math.sqrt(dx * dx + dy * dy + dz * dz);
        } catch (Throwable t) {
            return origin.distance(target.getLocation());
        }
    }

    /**
     * Angulo MINIMO entre el vector de mirada del player y cualquier punto
     * de la bounding box del target. Si el target esta dentro del cono de
     * mirada, devuelve un angulo pequeño aunque no este apuntando al centro.
     */
    private static double minAngleToHitbox(Location eye, Entity target) {
        try {
            org.bukkit.util.BoundingBox bb = target.getBoundingBox();
            Vector lookDir = eye.getDirection().normalize();
            // Sample los 8 corners + centro para tener buena estimacion sin
            // hacer un solver geometrico completo.
            double[][] pts = {
                {bb.getMinX(), bb.getMinY(), bb.getMinZ()},
                {bb.getMaxX(), bb.getMinY(), bb.getMinZ()},
                {bb.getMinX(), bb.getMaxY(), bb.getMinZ()},
                {bb.getMaxX(), bb.getMaxY(), bb.getMinZ()},
                {bb.getMinX(), bb.getMinY(), bb.getMaxZ()},
                {bb.getMaxX(), bb.getMinY(), bb.getMaxZ()},
                {bb.getMinX(), bb.getMaxY(), bb.getMaxZ()},
                {bb.getMaxX(), bb.getMaxY(), bb.getMaxZ()},
                {bb.getCenterX(), bb.getCenterY(), bb.getCenterZ()},
            };
            double minAngle = 180.0;
            for (double[] pt : pts) {
                Vector toPt = new Vector(pt[0] - eye.getX(), pt[1] - eye.getY(), pt[2] - eye.getZ());
                if (toPt.lengthSquared() < 0.0001) continue;
                toPt.normalize();
                double dot = Math.max(-1.0, Math.min(1.0, lookDir.dot(toPt)));
                double a = Math.toDegrees(Math.acos(dot));
                if (a < minAngle) minAngle = a;
            }
            return minAngle;
        } catch (Throwable t) {
            return 0;
        }
    }

    private static double clamp(double v, double lo, double hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    /**
     * Si target es un Player o Monster (zombie, pillager, etc.) cuenta como
     * "humano-like". Items, armor stands, paintings, vehicles no — esos no
     * son targets validos para killaura.
     */
    private static boolean isHumanLikeTarget(Entity t) {
        if (t instanceof Player) return true;
        if (t instanceof org.bukkit.entity.Monster) return true;
        if (t instanceof org.bukkit.entity.Animals) return true;
        return false;
    }

    /** Envia un mensaje de debug a consola + staff con permiso 'argus.alerts'. */
    private static void debugBroadcast(String raw) {
        String txt = org.bukkit.ChatColor.translateAlternateColorCodes('&', raw);
        for (Player op : org.bukkit.Bukkit.getOnlinePlayers()) {
            if (op.hasPermission("argus.alerts")) op.sendMessage(txt);
        }
        org.bukkit.Bukkit.getConsoleSender().sendMessage(txt);
    }

    /** Diferencia de yaw normalizada al rango [-180, 180]. */
    private static double yawDelta(float a, float b) {
        double d = (b - a) % 360.0;
        if (d > 180) d -= 360;
        if (d < -180) d += 360;
        return d;
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

        // Tracking de yaw para killaura_yaw_snap. Guardamos el yaw "publico"
        // (el que el cliente reporta via packet de movimiento) — la rotacion
        // visible para los demas. Si el server-side yaw difiere de este valor
        // en el momento de un hit, fue snap silencioso de killaura.
        s.lastMoveYaw       = to.getYaw();
        s.lastMovePitch     = to.getPitch();
        s.lastYawSampleMs   = System.currentTimeMillis();

        // Distancia horizontal recorrida en este move (no usamos delta de Y)
        double dx = to.getX() - from.getX();
        double dz = to.getZ() - from.getZ();
        double horizSq = dx * dx + dz * dz;

        // Speed check
        if (cfg.isCheckEnabled("speed")) {
            ConfigurationSection sec = cfg.checkSection("speed");
            double maxBps = sec != null ? sec.getDouble("max_blocks_per_sec", 10.0) : 10.0;
            // Acumular distancia en la ventana de 1 segundo
            long now = System.currentTimeMillis();
            s.distSamples.addLast(new double[]{now, Math.sqrt(horizSq)});
            while (!s.distSamples.isEmpty() && now - (long)s.distSamples.peekFirst()[0] > 1000L) {
                s.distSamples.pollFirst();
            }
            double accum = 0;
            for (double[] sample : s.distSamples) accum += sample[1];
            // Whitelist de excepciones legitimas:
            //   - Speed potion: hasta +4 b/s extra (Speed II vainilla = 8.97)
            //   - Elytra: hasta +30 b/s (gliding)
            //   - Vehiculos (caballo, bote, minecart): hasta +20 b/s
            //   - Hielo / hielo empacado / hielo azul: hasta +10 / +15 / +40 b/s
            //   - Soul Speed III sobre soul sand: hasta +3 b/s
            //   - Bouncing en slime: ignorado completamente (skip)
            boolean elytra = p.isGliding();
            boolean speedPotion = p.hasPotionEffect(PotionEffectType.SPEED);
            boolean vehicle = p.getVehicle() != null;
            org.bukkit.Material below = p.getLocation().clone().add(0, -0.1, 0).getBlock().getType();
            String belowName = below.name();
            boolean onSlime = belowName.equals("SLIME_BLOCK");
            double iceBonus = 0;
            if (belowName.equals("BLUE_ICE")) iceBonus = 40;
            else if (belowName.equals("PACKED_ICE")) iceBonus = 15;
            else if (belowName.equals("ICE") || belowName.equals("FROSTED_ICE")) iceBonus = 10;
            double effectiveMax = maxBps
                + (speedPotion ? 4.0 : 0)
                + (elytra ? 30 : 0)
                + (vehicle ? 20 : 0)
                + iceBonus;
            // Slime bouncing tiene picos enormes pero impredecibles, skipeamos
            // por completo el check para evitar falsos positivos.
            if (!onSlime && accum > effectiveMax) {
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

        // Jesus — caminar sobre agua sin sumergirse.
        //
        // FALSE POSITIVES comunes que tenemos que skipear:
        //  - Lily pad sobre agua (bloque solido pisable encima del agua).
        //  - Frost Walker enchant (convierte agua adyacente en hielo).
        //  - Bloques solidos puestos encima del agua (ej: cualquier bridge).
        //  - Ice / packed ice / blue ice / frosted ice en contacto.
        //  - Bubble columns elevando al jugador.
        //  - Boats fuera del water (ya skipeamos vehicle pero por las dudas).
        //
        // Solo flageamos si efectivamente NO hay nada solido entre los pies y
        // el agua, no esta en un bote, no tiene Frost Walker.
        if (cfg.isCheckEnabled("jesus")) {
            Block below   = to.clone().add(0, -0.05, 0).getBlock();
            Block belowDeep = to.clone().add(0, -0.5, 0).getBlock();
            Block at      = to.getBlock();
            boolean liquidBelow = below.isLiquid() || belowDeep.isLiquid();
            boolean inLiquid    = at.isLiquid();
            // Si el bloque debajo es un lily pad / hielo / cualquier solido,
            // NO es jesus.
            String belowName = below.getType().name();
            boolean solidBelow = !below.getType().isAir() && !below.isLiquid();
            boolean iceLike = belowName.contains("ICE") || belowName.equals("LILY_PAD")
                           || belowName.contains("FROSTED");
            boolean hasFrostWalker = false;
            try {
                org.bukkit.inventory.ItemStack boots = p.getInventory().getBoots();
                if (boots != null && boots.containsEnchantment(org.bukkit.enchantments.Enchantment.FROST_WALKER)) {
                    hasFrostWalker = true;
                }
            } catch (Throwable ignored) {}
            if (liquidBelow && !inLiquid && horizSq > 0.001
                && !solidBelow && !iceLike && !hasFrostWalker
                && !p.isGliding() && p.getVehicle() == null
                && !p.hasPotionEffect(PotionEffectType.WATER_BREATHING)) {
                s.jesusTicks++;
                if (s.jesusTicks > 8) {
                    mgr.flag(new Violation(p, "jesus", ViolationLevel.MID,
                        "caminando sobre liquido " + s.jesusTicks + " ticks"));
                    s.jesusTicks = 0;
                }
            } else {
                s.jesusTicks = 0;
            }
        }
    }

    /**
     * Loop 1 Hz: Fly check basado en delta-Y REAL entre samples.
     *
     * <p>El check viejo usaba {@code Player.getVelocity().getY()} para decidir
     * si el jugador estaba cayendo, pero ese metodo en Bukkit casi siempre
     * devuelve 0 (solo refleja velocity SETEADA por el server, no la real
     * resultante de gravedad). Eso producia falsos positivos al saltar desde
     * cualquier altura: el jugador caia con vy real ≈ -1.5 b/s pero Bukkit
     * reportaba vy=0.00 → flag spurio.
     *
     * <p>La version correcta compara {@code currentY - lastY} entre dos samples
     * consecutivas. Tambien skipea casos legitimos de "Y casi constante" que
     * no son fly: agua, lava, escaleras, vines, cobwebs, slime, slow_falling,
     * levitation, riding entity.
     */
    private void tick() {
        if (cfg == null || !cfg.isEnabled()) return;
        for (Player p : plugin.getServer().getOnlinePlayers()) {
            if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) continue;
            if (p.hasPermission("argus.ac.bypass")) continue;
            if (p.getAllowFlight() || p.isFlying()) continue;
            if (p.isGliding()) continue;
            if (p.getVehicle() != null) continue;

            PlayerState s = state(p);
            double currY = p.getLocation().getY();
            // Si es la primera muestra, inicializar y skipear este tick
            if (s.lastSampleY == Double.MIN_VALUE) {
                s.lastSampleY = currY;
                s.airTicks = 0;
                s.hoverTicks = 0;
                continue;
            }
            double dy = currY - s.lastSampleY;
            s.lastSampleY = currY;

            boolean onGround = p.isOnGround();
            if (onGround) {
                s.airTicks = 0;
                s.hoverTicks = 0;
                continue;
            }

            // Excepciones legitimas: cualquiera de estas y NO contamos airTicks
            if (isInLiquidOrClimbable(p) || hasFlyImmunityEffect(p)) {
                s.airTicks = 0;
                s.hoverTicks = 0;
                continue;
            }

            s.airTicks++;
            // HOVER REAL = Y casi constante (movimiento < 15 cm/seg en CUALQUIER
            // direccion). Si el jugador sube (salta a un bloque mas alto) o cae,
            // |dy| > 0.15 y NO es hover. El bug previo era contar como hover
            // cualquier dy >= -0.30, lo que incluia las subidas (saltos).
            if (Math.abs(dy) < 0.15) {
                s.hoverTicks++;
            } else {
                s.hoverTicks = 0;
            }

            if (!cfg.isCheckEnabled("fly")) continue;
            ConfigurationSection sec = cfg.checkSection("fly");
            int maxHoverSec   = sec != null ? sec.getInt("max_hover_seconds", 4) : 4;
            int minAirSeconds = sec != null ? sec.getInt("min_air_seconds_before_flag", 5) : 5;

            // Doble candado: flag SOLO si llevamos hover real Y suficiente
            // tiempo en el aire sin tocar piso (saltos vainilla nunca llegan
            // a >5s sin tocar suelo).
            if (s.hoverTicks >= maxHoverSec && s.airTicks >= minAirSeconds) {
                ViolationLevel lvl = s.hoverTicks >= 10 ? ViolationLevel.CRITICAL
                                   : s.hoverTicks >= 7  ? ViolationLevel.HIGH
                                                        : ViolationLevel.MID;
                mgr.flag(new Violation(p, "fly", lvl,
                    String.format("hover %ds (dy=%.2fb/s, airTicks=%d)",
                        s.hoverTicks, dy, s.airTicks)));
                s.hoverTicks = 0;
                s.airTicks = 0;
            }
        }
    }

    /** ¿Esta el player tocando agua, lava, escalera, vine, cobweb, scaffolding...? */
    private static boolean isInLiquidOrClimbable(Player p) {
        try {
            Location loc = p.getLocation();
            org.bukkit.block.Block at   = loc.getBlock();
            org.bukkit.block.Block head = loc.clone().add(0, p.getEyeHeight(), 0).getBlock();
            org.bukkit.block.Block below= loc.clone().add(0, -0.05, 0).getBlock();
            if (at.isLiquid() || head.isLiquid()) return true;
            Material[] climbables = {
                Material.LADDER, Material.VINE, Material.SCAFFOLDING,
                Material.COBWEB, Material.WEEPING_VINES, Material.WEEPING_VINES_PLANT,
                Material.TWISTING_VINES, Material.TWISTING_VINES_PLANT,
                Material.SWEET_BERRY_BUSH
            };
            for (Material m : climbables) {
                if (at.getType() == m || head.getType() == m || below.getType() == m) return true;
            }
            // Slime block / honey block / powder snow → tampoco es fly
            if (below.getType() == Material.SLIME_BLOCK
                || below.getType() == Material.HONEY_BLOCK
                || below.getType() == Material.POWDER_SNOW
                || at.getType()    == Material.POWDER_SNOW) {
                return true;
            }
            return false;
        } catch (Throwable t) {
            return false;
        }
    }

    /** ¿Tiene una pocion que justifique vy ≈ 0 en aire? */
    private static boolean hasFlyImmunityEffect(Player p) {
        try {
            return p.hasPotionEffect(PotionEffectType.SLOW_FALLING)
                || p.hasPotionEffect(PotionEffectType.LEVITATION);
        } catch (Throwable t) {
            return false;
        }
    }

    @EventHandler(ignoreCancelled = true, priority = EventPriority.MONITOR)
    public void onDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PlayerState s = state(p);
        if (e.getCause() == EntityDamageEvent.DamageCause.FALL) {
            s.lastFallDistance = 0f;
            // Cancela el flag pendiente del check nofall — el damage llego,
            // no fue NoFall.
            s.pendingNofallCheck = false;
        }
    }

    /**
     * NoFall — si el jugador toca suelo y NO tomo daño tras una caida grande.
     *
     * <p>CRITICO: el {@link EntityDamageEvent} de FALL puede llegar hasta 3
     * ticks DESPUES de que {@code isOnGround()} se vuelve true. Si flageamos
     * inmediato, vamos a falsear casi cualquier caida >6 bloques. Por eso
     * usamos un task delayed que verifica DESPUES si efectivamente no hubo
     * damage (es decir, {@code lastFallDistance} sigue > 0).
     *
     * <p>Tambien aplicamos whitelist de aterrizajes legitimos sin daño:
     * agua, lava, slime, hay, honey, cobweb, scaffolding, slow falling,
     * levitation, vehicle, water bucket usado.
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onLand(PlayerMoveEvent e) {
        if (!cfg.isCheckEnabled("nofall")) return;
        Player p = e.getPlayer();
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        if (p.getAllowFlight() || p.isFlying() || p.isGliding()) return;
        if (p.getVehicle() != null) return;
        PlayerState s = state(p);
        if (!p.isOnGround() || s.lastFallDistance <= 6.0f) return;
        // Snapshot inmediato y reset para no entrar 2 veces en este move
        final float fallDist = s.lastFallDistance;
        s.lastFallDistance = 0f;
        // Whitelist: si aterriza sobre / dentro de un bloque que cancela
        // el daño de caida vainilla, NO flagear nunca.
        if (landingNullifiesFallDamage(p)) return;
        if (hasFallImmunityEffect(p)) return;
        // El damage event de FALL puede llegar hasta 3 ticks despues. Esperamos
        // 4 ticks (200ms) y solo flageamos si Bukkit confirma que NO hubo
        // damage (marcamos via flag interno que onDamage limpia).
        s.pendingNofallCheck = true;
        plugin.getServer().getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline()) return;
            PlayerState s2 = state(p);
            if (!s2.pendingNofallCheck) return;  // damage llegó, todo OK
            s2.pendingNofallCheck = false;
            // Re-chequear whitelist por si entro a agua despues
            if (landingNullifiesFallDamage(p)) return;
            if (hasFallImmunityEffect(p)) return;
            // Confirmado: cayo X bloques sin daño = NoFall
            ViolationLevel lvl = fallDist > 20.0f ? ViolationLevel.HIGH
                                                   : ViolationLevel.MID;
            mgr.flag(new Violation(p, "nofall", lvl,
                String.format("cayo %.1fb sin daño", fallDist)));
        }, 4L);
    }

    /** Devuelve true si el jugador aterrizo en un bloque que cancela el FALL damage. */
    private static boolean landingNullifiesFallDamage(Player p) {
        try {
            org.bukkit.Location loc = p.getLocation();
            org.bukkit.block.Block at    = loc.getBlock();
            org.bukkit.block.Block below = loc.clone().add(0, -0.5, 0).getBlock();
            org.bukkit.block.Block under = loc.clone().add(0, -1.2, 0).getBlock();
            String[] names = {at.getType().name(), below.getType().name(), under.getType().name()};
            for (String n : names) {
                if (n.equals("WATER") || n.equals("LAVA")
                    || n.equals("SLIME_BLOCK") || n.equals("HAY_BLOCK")
                    || n.equals("HONEY_BLOCK") || n.equals("COBWEB")
                    || n.equals("SCAFFOLDING") || n.equals("LADDER")
                    || n.equals("VINE") || n.equals("SWEET_BERRY_BUSH")
                    || n.equals("POWDER_SNOW") || n.equals("BUBBLE_COLUMN")
                    || n.equals("SEAGRASS") || n.equals("TALL_SEAGRASS")
                    || n.equals("KELP") || n.equals("KELP_PLANT")) return true;
            }
        } catch (Exception ignored) {}
        return false;
    }

    /** Slow Falling, Levitation y similares cancelan el FALL damage. */
    private static boolean hasFallImmunityEffect(Player p) {
        try {
            return p.hasPotionEffect(PotionEffectType.SLOW_FALLING)
                || p.hasPotionEffect(PotionEffectType.LEVITATION);
        } catch (Exception ignored) { return false; }
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Scaffold — colocar bloque mirando hacia abajo mientras se mueve
    // ─────────────────────────────────────────────────────────────────────

    /**
     * Scaffold detection.
     *
     * <p>Distinguir scaffold cheat de construccion normal es complicado.
     * Construir un piso vainilla: pitch alto + placements debajo + frecuencia
     * alta — los 3 trigger ingenuos. Scaffold cheat se diferencia porque el
     * jugador esta SUSPENDIDO EN EL AIRE sostenido SOLO por los bloques que
     * el mismo va poniendo (typical pattern: caminar hacia atras sobre nada,
     * el cheat coloca el bloque siguiente que lo sostiene).
     *
     * <p>Criterios estrictos para flag:
     * <ol>
     *   <li>pitch > 70 (mirando casi recto abajo, no construyendo a 45 grados)</li>
     *   <li>{@code !isOnGround()} (esta en el aire al colocar)</li>
     *   <li>el bloque debajo de sus pies era AIR antes del placement (no
     *       hay suelo solido sosteniendolo)</li>
     *   <li>>= 6 placements consecutivos cumpliendo lo anterior en 2s</li>
     * </ol>
     */
    @EventHandler(ignoreCancelled = true, priority = EventPriority.MONITOR)
    public void onPlace(BlockPlaceEvent e) {
        if (!cfg.isCheckEnabled("scaffold")) return;
        Player p = e.getPlayer();
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return;
        if (p.hasPermission("argus.ac.bypass")) return;

        ConfigurationSection sec = cfg.checkSection("scaffold");
        float minPitch  = sec != null ? (float) sec.getDouble("min_pitch_deg", 70.0) : 70f;
        long  windowMs  = sec != null ? sec.getLong("window_ms", 2000L) : 2000L;
        int   minHits   = sec != null ? sec.getInt("min_hits", 6) : 6;

        float pitch = p.getLocation().getPitch();
        if (pitch < minPitch) return;

        Block placed = e.getBlockPlaced();
        Location pl  = p.getLocation();
        if (placed.getY() > pl.getY()) return;

        // Criterio fuerte: el jugador esta en el aire Y no hay suelo solido
        // bajo sus pies (excluyendo el bloque que acaba de colocar). Esto
        // distingue scaffold cheat de construir un piso normal sobre suelo.
        if (p.isOnGround()) return;
        Block belowFeet = pl.clone().add(0, -0.2, 0).getBlock();
        Block twoBelow  = pl.clone().add(0, -1.2, 0).getBlock();
        // Si el bloque debajo NO es aire ni el bloque que acaba de poner,
        // hay suelo solido = construccion normal.
        if (!belowFeet.getType().isAir() && !belowFeet.equals(placed)) return;
        if (!twoBelow.getType().isAir() && !twoBelow.equals(placed)) return;

        PlayerState s = state(p);
        long now = System.currentTimeMillis();
        s.scaffoldHits.addLast(now);
        while (!s.scaffoldHits.isEmpty() && now - s.scaffoldHits.peekFirst() > windowMs) {
            s.scaffoldHits.pollFirst();
        }
        if (s.scaffoldHits.size() >= minHits) {
            ViolationLevel lvl = s.scaffoldHits.size() >= (minHits * 2) ? ViolationLevel.HIGH
                                                                       : ViolationLevel.MID;
            mgr.flag(new Violation(p, "scaffold", lvl,
                s.scaffoldHits.size() + " placements en aire en " + (windowMs/1000) + "s, pitch=" + (int)pitch));
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
        if (p.hasPermission("argus.ac.bypass")) return;
        PlayerState s = state(p);
        if (s.eatStartedMs <= 0) return;
        long elapsed = System.currentTimeMillis() - s.eatStartedMs;
        s.eatStartedMs = 0;
        Material itemType = e.getItem().getType();
        String n = itemType.name();
        // Whitelist: items que se "consumen" instantaneo o casi:
        //  - Totem of Undying (uso, no eat) - pero ya filtramos por isEdible
        //  - Honey bottle es 40 ticks (2s)
        //  - Milk bucket es 32 ticks (1.6s)
        //  - Potions (drinkable) son 32 ticks
        //  - Suspicious stew, cake (no se "comen" en mano), etc.
        if (n.contains("BUCKET") || n.contains("POTION")) return;
        ConfigurationSection sec = cfg.checkSection("fasteat");
        long min = sec != null ? sec.getLong("min_eat_ms", 1200L) : 1200L;
        // Threshold mas bajo (1200ms) — algunos items legitimos demoran ~1300ms
        // por jitter de red. Solo flagamos si elapsed es REALMENTE bajo.
        if (elapsed < min) {
            ViolationLevel lvl = elapsed < min / 3 ? ViolationLevel.HIGH
                              : elapsed < min / 2 ? ViolationLevel.MID
                                                  : ViolationLevel.LOW;
            mgr.flag(new Violation(p, "fasteat", lvl,
                "comio " + itemType.name() + " en " + elapsed + "ms"));
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
        // Subido a 7 msgs/5s: en una conversacion intensa o discusion en
        // chat publico se pueden enviar 5-6 mensajes cortos en 5s
        // legitimamente. Ya bot mass-spam suele ser >10/5s.
        int max = sec != null ? sec.getInt("max_msgs_per_5s", 7) : 7;
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
        // Skip commands del propio AC, /msg, /reply (legitimas), y /spawn-like
        // que un jugador puede ejecutar varias veces en pelea.
        String cmd = e.getMessage().split(" ", 2)[0].toLowerCase();
        if (cmd.startsWith("/argus") || cmd.equals("/msg") || cmd.equals("/r")
            || cmd.equals("/tell") || cmd.equals("/w") || cmd.equals("/reply")
            || cmd.equals("/spawn") || cmd.equals("/sethome") || cmd.equals("/home")) return;
        PlayerState s = state(p);
        long now = System.currentTimeMillis();
        s.cmdTimes.addLast(now);
        while (!s.cmdTimes.isEmpty() && now - s.cmdTimes.peekFirst() > 5000L) {
            s.cmdTimes.pollFirst();
        }
        ConfigurationSection sec = cfg.checkSection("cmd_spam");
        // Subido a 12 cmds/5s. Macros legitimos (/feed, /heal, /near, /tpa)
        // pueden hacer ratios altos en 1-2s.
        int max = sec != null ? sec.getInt("max_cmds_per_5s", 12) : 12;
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
        // Solo evaluamos clicks en el propio inventario del player. Si abre
        // un chest/furnace/etc, no aplica.
        if (e.getInventory().getHolder() != null && !(e.getInventory().getHolder() instanceof Player)) return;

        PlayerState s = state(p);
        long now = System.currentTimeMillis();
        // Distancia recorrida en los ultimos 300ms (la ventana corta filtra
        // movimiento previo a abrir el inventario).
        double recentDist = 0;
        for (double[] sample : s.distSamples) {
            if (now - (long)sample[0] < 300L) recentDist += sample[1];
        }
        // En PvP 1.8 (clientes Lunar/Vape clientes), hacer "fast pearl/gap"
        // requiere mover items mientras corres. Es legitimo. 5 bloques en
        // 300ms (~16 b/s) es ya fast-mode bunny hop con cheats.
        if (recentDist > 5.0) {
            mgr.flag(new Violation(p, "inventory_move", ViolationLevel.LOW,
                String.format("inv click + %.1fb en 0.3s", recentDist)));
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSneak(PlayerToggleSneakEvent e) {
        // Hook reservado para futuros checks (ej: detectar AutoSneak).
    }

    /**
     * Track del ultimo swing de brazo. El cliente vainilla SIEMPRE envia
     * Animation packet (SWING_MAIN_HAND) ANTES de un EntityDamageByEntity.
     * Muchos cheats killaura "silent" no replican esto correctamente.
     */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onAnimation(PlayerAnimationEvent e) {
        Player p = e.getPlayer();
        state(p).lastSwingMs = System.currentTimeMillis();
    }

    // ─────────────────────────────────────────────────────────────────────
    //  Estado por jugador
    // ─────────────────────────────────────────────────────────────────────

    private static final class PlayerState {
        // Combat
        final Deque<Long> attackTimes = new ArrayDeque<>();
        final Deque<Long> attackIntervals = new ArrayDeque<>(); // ms entre hits, para varianza
        long lastAttackMs = 0;
        long lastSwingMs = 0;  // PlayerAnimationEvent timestamp
        // Multi-target killaura: cada entrada = [tsMs, uuidMSB, uuidLSB]
        final Deque<long[]> recentTargets = new ArrayDeque<>();
        // Yaw snap detection
        float lastMoveYaw   = 0f;
        float lastMovePitch = 0f;
        long  lastYawSampleMs = 0L;
        // Movement
        final Deque<double[]> distSamples = new ArrayDeque<>(); // [tsMs, distHoriz]
        int  airTicks = 0;
        int  hoverTicks = 0;
        double lastSampleY = Double.MIN_VALUE;
        float lastFallDistance = 0f;
        // Pack 44.1: Si true, hay un nofall delayed task pendiente. onDamage
        // (FALL) lo desactiva si el damage llego. Si sigue true tras 4 ticks,
        // confirmamos NoFall y flageamos.
        boolean pendingNofallCheck = false;
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
