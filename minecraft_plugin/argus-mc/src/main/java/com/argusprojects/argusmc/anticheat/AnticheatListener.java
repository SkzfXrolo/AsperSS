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

public final class AnticheatListener implements Listener {

    private final ArgusPlugin plugin;
    private final ViolationManager mgr;
    private final AnticheatConfig cfg;

    private final Map<UUID, PlayerState> states = new HashMap<>();

    public static volatile boolean debugMode = false;

    private final BukkitTask repeatingTask;

    public AnticheatListener(ArgusPlugin plugin, ViolationManager mgr) {
        this.plugin = plugin;
        this.mgr    = mgr;
        this.cfg    = plugin.getAnticheatConfig();
        this.repeatingTask = plugin.getServer().getScheduler().runTaskTimer(
            plugin, this::tick, 20L, 20L);
    }

    public void shutdown() {
        if (repeatingTask != null) repeatingTask.cancel();
    }

    private PlayerState state(Player p) {
        return states.computeIfAbsent(p.getUniqueId(), k -> new PlayerState());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent e) {
        Player p = e.getPlayer();
        states.put(p.getUniqueId(), new PlayerState());

        if (mgr.hasPendingForcedSs(p.getUniqueId())) {
            mgr.consumePendingForcedSs(p);
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        states.remove(e.getPlayer().getUniqueId());
        plugin.getAutoClickEngine().remove(e.getPlayer().getUniqueId());
        mgr.onPlayerQuit(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onDeath(PlayerDeathEvent e) {

        Player p = e.getEntity();
        PlayerState s = state(p);
        s.airTicks = 0;
        s.lastFallDistance = 0f;
    }

    @EventHandler(ignoreCancelled = true, priority = EventPriority.MONITOR)
    public void onAttack(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof Player attacker)) return;

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

        if (target instanceof org.bukkit.entity.Item
            || target instanceof org.bukkit.entity.AreaEffectCloud
            || target instanceof org.bukkit.entity.ExperienceOrb
            || target instanceof org.bukkit.entity.LightningStrike) return;

        if (target.getUniqueId().equals(attacker.getUniqueId())) return;

        boolean isMeleeHit = (e.getCause() == EntityDamageEvent.DamageCause.ENTITY_ATTACK
                           || e.getCause() == EntityDamageEvent.DamageCause.ENTITY_SWEEP_ATTACK);

        if (cfg.isCheckEnabled("killaura_no_swing") && isMeleeHit && s.lastSwingMs > 0
            && e.getCause() != EntityDamageEvent.DamageCause.ENTITY_SWEEP_ATTACK) {
            ConfigurationSection sec = cfg.checkSection("killaura_no_swing");
            long maxAge = sec != null ? sec.getLong("max_swing_age_ms", 600L) : 600L;
            // Clientes 1.9+ mandan el swing DESPUES del ataque (se procesa en el mismo tick):
            // se evalua un tick despues para contarlo.
            org.bukkit.Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (!attacker.isOnline() || s.lastSwingMs >= now) return;
                long swingAge = now - s.lastSwingMs;
                if (swingAge > maxAge) {
                    ViolationLevel lvl = swingAge > 5000 ? ViolationLevel.HIGH
                                                         : ViolationLevel.MID;
                    mgr.flag(new Violation(attacker, "killaura_no_swing", lvl,
                        "swing fue hace " + swingAge + "ms (max " + maxAge + "ms)"));
                }
            }, 1L);
        }

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

        if (cfg.isCheckEnabled("reach") && isMeleeHit) {
            ConfigurationSection sec = cfg.checkSection("reach");
            double maxDist = sec != null ? sec.getDouble("max_distance", 4.5) : 4.5;
            double dist = closestDistanceToEntity(attacker.getEyeLocation(), target);

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

        if (cfg.isCheckEnabled("killaura_yaw_snap") && isMeleeHit) {
            ConfigurationSection sec = cfg.checkSection("killaura_yaw_snap");
            double maxDelta = sec != null ? sec.getDouble("max_delta_deg", 130.0) : 130.0;
            long maxAgeMs   = sec != null ? sec.getLong("max_age_ms", 200L) : 200L;
            if (s.lastYawSampleMs > 0 && now - s.lastYawSampleMs <= maxAgeMs) {
                float currentYaw = attacker.getLocation().getYaw();
                double delta = Math.abs(yawDelta(s.lastMoveYaw, currentYaw));
                if (delta > maxDelta) {

                    double dxT = target.getLocation().getX() - attacker.getLocation().getX();
                    double dzT = target.getLocation().getZ() - attacker.getLocation().getZ();
                    float expectedYaw = (float) (Math.toDegrees(Math.atan2(-dxT, dzT)));
                    double misalign = Math.abs(yawDelta(currentYaw, expectedYaw));

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
            } catch (Exception ex) {  }
        }

        if (isMeleeHit) {
            s.lastAttackMs = now;
            s.attackTimes.addLast(now);
            while (!s.attackTimes.isEmpty() && now - s.attackTimes.peekFirst() > 1000L) {
                s.attackTimes.pollFirst();
            }
            plugin.getAutoClickEngine().onAttack(attacker, now, mgr::flag);
        }
    }

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

    private static double minAngleToHitbox(Location eye, Entity target) {
        try {
            org.bukkit.util.BoundingBox bb = target.getBoundingBox();
            Vector lookDir = eye.getDirection().normalize();

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

    private static boolean isHumanLikeTarget(Entity t) {
        if (t instanceof Player) return true;
        if (t instanceof org.bukkit.entity.Monster) return true;
        if (t instanceof org.bukkit.entity.Animals) return true;
        return false;
    }

    private static void debugBroadcast(String raw) {
        String txt = org.bukkit.ChatColor.translateAlternateColorCodes('&', raw);
        for (Player op : org.bukkit.Bukkit.getOnlinePlayers()) {
            if (op.hasPermission("argus.alerts")) op.sendMessage(txt);
        }
        org.bukkit.Bukkit.getConsoleSender().sendMessage(txt);
    }

    private static double yawDelta(float a, float b) {
        double d = (b - a) % 360.0;
        if (d > 180) d -= 360;
        if (d < -180) d += 360;
        return d;
    }

    @EventHandler(ignoreCancelled = true, priority = EventPriority.MONITOR)
    public void onMove(PlayerMoveEvent e) {
        Player p = e.getPlayer();
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return;
        if (p.hasPermission("argus.ac.bypass")) return;

        PlayerState s = state(p);
        Location from = e.getFrom();
        Location to   = e.getTo();
        if (to == null) return;

        if (p.isOnGround()) s.lastGroundMs = System.currentTimeMillis();
        s.lastMoveYaw       = to.getYaw();
        s.lastMovePitch     = to.getPitch();
        s.lastYawSampleMs   = System.currentTimeMillis();

        double dx = to.getX() - from.getX();
        double dz = to.getZ() - from.getZ();
        double horizSq = dx * dx + dz * dz;

        if (cfg.isCheckEnabled("speed")) {
            ConfigurationSection sec = cfg.checkSection("speed");
            double maxBps = sec != null ? sec.getDouble("max_blocks_per_sec", 10.0) : 10.0;

            long now = System.currentTimeMillis();
            s.distSamples.addLast(new double[]{now, Math.sqrt(horizSq)});
            while (!s.distSamples.isEmpty() && now - (long)s.distSamples.peekFirst()[0] > 1000L) {
                s.distSamples.pollFirst();
            }
            double accum = 0;
            for (double[] sample : s.distSamples) accum += sample[1];

            // El impulso del planeo sigue un rato despues de cerrar la elytra.
            if (p.isGliding()) s.lastGlidingMs = now;
            boolean elytra = now - s.lastGlidingMs <= 2000L;
            boolean speedPotion = p.hasPotionEffect(PotionEffectType.SPEED);
            boolean vehicle = p.getVehicle() != null;
            org.bukkit.Material below = p.getLocation().clone().add(0, -0.1, 0).getBlock().getType();
            String belowName = below.name();
            boolean onSlime = belowName.equals("SLIME_BLOCK");
            double iceBonus = 0;
            if (belowName.equals("BLUE_ICE")) iceBonus = 40;
            else if (belowName.equals("PACKED_ICE")) iceBonus = 15;
            else if (belowName.equals("ICE") || belowName.equals("FROSTED_ICE")) iceBonus = 10;
            // El impulso del hielo sigue en el aire (saltando) y un rato despues de salir.
            if (iceBonus > 0) {
                s.lastOnIceMs = now;
                s.lastIceBonus = iceBonus;
            } else if (now - s.lastOnIceMs <= 1500L) {
                iceBonus = s.lastIceBonus;
            }
            double effectiveMax = maxBps
                + (speedPotion ? 4.0 : 0)
                + (elytra ? 30 : 0)
                + (vehicle ? 20 : 0)
                + iceBonus;

            if (!onSlime && accum > effectiveMax) {
                ViolationLevel lvl;
                if (accum > effectiveMax * 2.0)   lvl = ViolationLevel.HIGH;
                else if (accum > effectiveMax * 1.4) lvl = ViolationLevel.MID;
                else                              lvl = ViolationLevel.LOW;
                mgr.flag(new Violation(p, "speed", lvl,
                    String.format("%.1fbps (max=%.1f)", accum, effectiveMax)));
            }
        }

        if (p.getFallDistance() > s.lastFallDistance) {
            s.lastFallDistance = p.getFallDistance();
        }

        if (cfg.isCheckEnabled("jesus")) {
            Block below   = to.clone().add(0, -0.05, 0).getBlock();
            Block belowDeep = to.clone().add(0, -0.5, 0).getBlock();
            Block at      = to.getBlock();
            boolean liquidBelow = below.isLiquid() || belowDeep.isLiquid();
            boolean inLiquid    = at.isLiquid();

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

            if (s.lastSampleY == Double.MIN_VALUE) {
                s.lastSampleY = currY;
                s.airTicks = 0;
                s.hoverTicks = 0;
                continue;
            }
            double dy = currY - s.lastSampleY;
            s.lastSampleY = currY;

            // Tocar el piso ENTRE muestras (saltar en el lugar) o recibir knockback (combos)
            // no es volar, aunque en el instante de la muestra este en el aire.
            long nowMs = System.currentTimeMillis();
            boolean onGround = p.isOnGround() || nowMs - s.lastGroundMs < 1100L || nowMs - s.lastHurtMs < 1500L;
            if (onGround) {
                s.airTicks = 0;
                s.hoverTicks = 0;
                continue;
            }

            if (isInLiquidOrClimbable(p) || hasFlyImmunityEffect(p)) {
                s.airTicks = 0;
                s.hoverTicks = 0;
                continue;
            }

            s.airTicks++;

            if (Math.abs(dy) < 0.15) {
                s.hoverTicks++;
            } else {
                s.hoverTicks = 0;
            }

            if (!cfg.isCheckEnabled("fly")) continue;
            ConfigurationSection sec = cfg.checkSection("fly");
            int maxHoverSec   = sec != null ? sec.getInt("max_hover_seconds", 4) : 4;
            int minAirSeconds = sec != null ? sec.getInt("min_air_seconds_before_flag", 5) : 5;

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
        s.lastHurtMs = System.currentTimeMillis();
        if (e.getCause() == EntityDamageEvent.DamageCause.FALL) {
            s.lastFallDistance = 0f;

            s.pendingNofallCheck = false;
        }
    }

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

        final float fallDist = s.lastFallDistance;
        s.lastFallDistance = 0f;

        if (landingNullifiesFallDamage(p)) return;
        if (hasFallImmunityEffect(p)) return;

        s.pendingNofallCheck = true;
        plugin.getServer().getScheduler().runTaskLater(plugin, () -> {
            if (!p.isOnline()) return;
            PlayerState s2 = state(p);
            if (!s2.pendingNofallCheck) return;
            s2.pendingNofallCheck = false;

            if (landingNullifiesFallDamage(p)) return;
            if (hasFallImmunityEffect(p)) return;

            ViolationLevel lvl = fallDist > 20.0f ? ViolationLevel.HIGH
                                                   : ViolationLevel.MID;
            mgr.flag(new Violation(p, "nofall", lvl,
                String.format("cayo %.1fb sin daño", fallDist)));
        }, 4L);
    }

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

    private static boolean hasFallImmunityEffect(Player p) {
        try {
            return p.hasPotionEffect(PotionEffectType.SLOW_FALLING)
                || p.hasPotionEffect(PotionEffectType.LEVITATION);
        } catch (Exception ignored) { return false; }
    }

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

        if (p.isOnGround()) return;
        Block belowFeet = pl.clone().add(0, -0.2, 0).getBlock();
        Block twoBelow  = pl.clone().add(0, -1.2, 0).getBlock();

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

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteract(PlayerInteractEvent e) {
        if (!cfg.isCheckEnabled("fasteat")) return;
        if (e.getItem() == null) return;
        Material mat = e.getItem().getType();
        if (!isEdible(mat)) return;

        // Click derecho repetido mientras ya come (comun en 1.8) no reinicia el tiempo de comida.
        if (e.getPlayer().isHandRaised() && state(e.getPlayer()).eatStartedMs > 0) return;
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

        if (n.contains("BUCKET") || n.contains("POTION")) return;
        ConfigurationSection sec = cfg.checkSection("fasteat");
        long min = sec != null ? sec.getLong("min_eat_ms", 1200L) : 1200L;

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

        int max = sec != null ? sec.getInt("max_cmds_per_5s", 12) : 12;
        if (s.cmdTimes.size() > max) {
            ViolationLevel lvl = s.cmdTimes.size() > max * 2 ? ViolationLevel.MID
                                                             : ViolationLevel.LOW;
            mgr.flag(new Violation(p, "cmd_spam", lvl,
                s.cmdTimes.size() + " cmds/5s (max=" + max + ")"));
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInvClick(InventoryClickEvent e) {
        if (!cfg.isCheckEnabled("inventory_move")) return;
        if (!(e.getWhoClicked() instanceof Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;

        if (e.getInventory().getHolder() != null && !(e.getInventory().getHolder() instanceof Player)) return;

        PlayerState s = state(p);
        long now = System.currentTimeMillis();

        double recentDist = 0;
        for (double[] sample : s.distSamples) {
            if (now - (long)sample[0] < 300L) recentDist += sample[1];
        }

        if (recentDist > 5.0) {
            mgr.flag(new Violation(p, "inventory_move", ViolationLevel.LOW,
                String.format("inv click + %.1fb en 0.3s", recentDist)));
        }
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onSneak(PlayerToggleSneakEvent e) {

    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onAnimation(PlayerAnimationEvent e) {
        if (e.getAnimationType() != org.bukkit.event.player.PlayerAnimationType.ARM_SWING) return;
        Player p = e.getPlayer();
        if (p.getGameMode() == GameMode.CREATIVE || p.getGameMode() == GameMode.SPECTATOR) return;
        if (p.hasPermission("argus.ac.bypass")) return;

        PlayerState s = state(p);
        long now = System.currentTimeMillis();
        s.lastSwingMs = now;
        plugin.getAutoClickEngine().onSwing(p, now, mgr::flag);
    }

    private static final class PlayerState {

        final Deque<Long> attackTimes = new ArrayDeque<>();
        long lastAttackMs = 0;
        long lastSwingMs = 0;

        final Deque<long[]> recentTargets = new ArrayDeque<>();

        float lastMoveYaw   = 0f;
        float lastMovePitch = 0f;
        long  lastYawSampleMs = 0L;

        final Deque<double[]> distSamples = new ArrayDeque<>();
        long lastOnIceMs;
        long lastGroundMs;
        long lastHurtMs;
        long lastGlidingMs;
        double lastIceBonus;
        int  airTicks = 0;
        int  hoverTicks = 0;
        double lastSampleY = Double.MIN_VALUE;
        float lastFallDistance = 0f;

        boolean pendingNofallCheck = false;
        int  jesusTicks = 0;

        final Deque<Long> scaffoldHits = new ArrayDeque<>();

        long eatStartedMs = 0;

        final Deque<Long> chatTimes = new ArrayDeque<>();
        final Deque<Long> cmdTimes  = new ArrayDeque<>();
    }
}
