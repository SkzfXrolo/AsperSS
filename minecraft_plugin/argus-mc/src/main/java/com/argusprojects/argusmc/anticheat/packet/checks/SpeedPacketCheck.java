package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

public final class SpeedPacketCheck {

    private static final double VANILLA_SPRINT_BPS = 5.612;
    private static final double STRAFE_JUMP_HEADROOM = 1.45;

    private final ArgusPlugin plugin;

    public SpeedPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     long now, boolean onGround,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("speed_packet")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "speed_packet")) return;
        if (plugin.getWarmupGracePeriod().inGrace(player, "speed_packet")) return;
        if (s.teleporting) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return;

        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.getAllowFlight() && player.isFlying()) return;
        if (player.isInsideVehicle()) return;
        if (player.isGliding()) return;
        if (player.isSwimming()) return;
        if (player.isInWater()) return;
        if (player.isClimbing()) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("speed_packet");
        // Antes de la exencion de combate y del filtro de dt: pegar no da velocidad (el knockback
        // recibido ya exime via lastDamageTakenMs) y descartar paquetes subestimaria el promedio.
        checkSustained(player, s, Math.hypot(nx - s.lastX, nz - s.lastZ), now, sec, sink);

        if (isInCombat(s, now)) return;

        double baseCap = sec != null ? sec.getDouble("max_bps", 7.8) : 7.8;
        int consecutiveToFlag = sec != null ? sec.getInt("consecutive_to_flag", 5) : 5;
        long minDtMs = sec != null ? sec.getLong("min_dt_ms", 45L) : 45L;
        long flagCooldownMs = sec != null ? sec.getLong("flag_cooldown_ms", 2_000L) : 2_000L;
        double overflowRatio = sec != null ? sec.getDouble("overflow_ratio", 1.08) : 1.08;

        long dt = now - s.lastMoveMs;
        if (dt < minDtMs || dt > 250L) return;

        double dx = nx - s.lastX;
        double dz = nz - s.lastZ;
        double dh = Math.sqrt(dx * dx + dz * dz);
        if (dh < 0.05) return;

        double bps = dh * 1000.0 / dt;


        double allowance = 1.0;
        if (player.isSprinting()) allowance *= 1.12;
        if (!onGround) allowance *= 1.10;
        PotionEffect speed = getEffect(player, "SPEED");
        if (speed != null) allowance *= 1.0 + 0.20 * (speed.getAmplifier() + 1);
        if (isOnIce(player)) allowance *= 1.40;
        if (isOnSoulSpeed(player)) allowance *= 1.40;

        double cap = Math.max(baseCap, VANILLA_SPRINT_BPS * STRAFE_JUMP_HEADROOM) * allowance;
        double triggerCap = cap * overflowRatio;

        if (bps > triggerCap) {
            s.speedOverflowCounter++;
        } else {
            s.speedOverflowCounter = Math.max(0, s.speedOverflowCounter - 2);
        }

        if (s.speedOverflowCounter < consecutiveToFlag) return;
        if (now - s.lastSpeedFlagMs < flagCooldownMs) {
            s.speedOverflowCounter = consecutiveToFlag - 1;
            return;
        }

        ViolationLevel lvl;
        if (bps > cap * 1.75) {
            lvl = ViolationLevel.HIGH;
        } else if (bps > cap * 1.40) {
            lvl = ViolationLevel.MID;
        } else {
            lvl = ViolationLevel.LOW;
        }
        sink.flag(new Violation(player, "speed_packet",
            lvl,
            String.format("bps=%.2f cap=%.2f allow=%.2f streak=%d", bps, cap, allowance, s.speedOverflowCounter)));

        s.speedOverflowCounter = 0;
        s.lastSpeedFlagMs = now;
    }

    /**
     * Promedio sostenido en 1s: el pico por tick de un sprint-jump legit llega a ~12 bps (por eso el
     * check por tick es tolerante), pero el promedio vanilla no pasa de ~7.3 bps (headhitter ~8.5).
     */
    private void checkSustained(Player player, PacketDataStore.State s, double dh, long now,
                                ConfigurationSection sec, ViolationSink sink) {
        if (isOnIce(player) || isOnSoulSpeed(player) || now - s.lastDamageTakenMs < 2_000L) s.speedExemptMs = now;
        java.util.ArrayDeque<double[]> win = s.speedWindow;
        double[] last = win.peekLast();
        if (last != null && now - (long) last[0] > 250L) {
            win.clear();
            s.speedWindowStartMs = 0L;
        }
        win.addLast(new double[]{now, dh});
        while (!win.isEmpty() && now - (long) win.peekFirst()[0] > 1_000L) {
            s.speedWindowStartMs = (long) win.pollFirst()[0];
        }
        if (s.speedWindowStartMs == 0L || now - s.speedExemptMs < 2_000L) return;

        double sum = 0;
        for (double[] e : win) sum += e[1];
        double avgBps = sum * 1000.0 / (now - s.speedWindowStartMs);

        double cap = sec != null ? sec.getDouble("avg_max_bps", 9.3) : 9.3;
        PotionEffect speed = getEffect(player, "SPEED");
        if (speed != null) cap *= 1.0 + 0.20 * (speed.getAmplifier() + 1);
        if (avgBps <= cap) return;
        long cooldown = sec != null ? sec.getLong("flag_cooldown_ms", 2_000L) : 2_000L;
        if (now - s.lastSpeedAvgFlagMs < cooldown) return;
        s.lastSpeedAvgFlagMs = now;
        ViolationLevel lvl = avgBps > cap * 1.3 ? ViolationLevel.HIGH : ViolationLevel.MID;
        sink.flag(new Violation(player, "speed_packet", lvl,
            String.format("promedio 1s=%.2f bps (max %.2f)", avgBps, cap)));
    }

    private static boolean isInCombat(PacketDataStore.State s, long now) {
        int combatGraceMs = 600;
        if (s.lastAttackMs > 0 && now - s.lastAttackMs < combatGraceMs) return true;
        if (s.lastSwingMs > 0 && now - s.lastSwingMs < combatGraceMs) return true;
        if (s.recentAttacksWithin(1_000L, now) >= 5) return true;
        if (s.recentSwingsWithin(1_000L, now) >= 6) return true;
        return false;
    }

    private static PotionEffect getEffect(Player p, String name) {
        try {
            @SuppressWarnings("deprecation")
            PotionEffectType type = PotionEffectType.getByName(name);
            if (type == null) return null;
            return p.getPotionEffect(type);
        } catch (Throwable t) {
            return null;
        }
    }

    private static boolean isOnIce(Player p) {
        try {
            Material below = p.getLocation().clone().add(0, -0.1, 0).getBlock().getType();
            return below == Material.ICE || below == Material.PACKED_ICE
                || below == Material.BLUE_ICE || below == Material.FROSTED_ICE;
        } catch (Throwable t) {
            return false;
        }
    }

    private static boolean isOnSoulSpeed(Player p) {
        try {
            Material below = p.getLocation().clone().add(0, -0.1, 0).getBlock().getType();
            boolean blockOk = below == Material.SOUL_SAND || below == Material.SOUL_SOIL;
            if (!blockOk) return false;

            var boots = p.getInventory().getBoots();
            if (boots == null) return false;
            for (var ench : boots.getEnchantments().keySet()) {
                if (ench.getKey().getKey().equalsIgnoreCase("soul_speed")) return true;
            }
            return false;
        } catch (Throwable t) {
            return false;
        }
    }
}
