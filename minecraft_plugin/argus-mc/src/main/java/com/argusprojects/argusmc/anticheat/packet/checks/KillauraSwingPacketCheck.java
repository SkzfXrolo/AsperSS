package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/**
 * Pack 47 — Killaura por timing de swing vs interact.
 *
 * <p>Un cliente vanilla envia SIEMPRE un packet Animation (swing) ANTES de
 * un InteractEntity(ATTACK). Killauras simples disparan el InteractEntity
 * sin animation, o con &gt;100ms de delay. Detecciones:
 *
 * <ul>
 *   <li>Attack sin swing previo en los ultimos 250ms → killaura_no_swing</li>
 *   <li>Swing repetido sin attack y sin click derecho/lanzar → suspicious
 *       autoclicker (lo cubre CPS check)</li>
 * </ul>
 *
 * <p>Tambien validamos que el atacante NO esté completamente fuera del FOV
 * del target a nivel rotation (yaw delta &gt; 90° = hit imposible de hacer
 * naturalmente sin aim assist).
 */
public final class KillauraSwingPacketCheck {

    private static final long DEFAULT_SWING_WINDOW_MS = 250L;
    private static final double DEFAULT_FOV_DEG = 90.0;

    private final ArgusPlugin plugin;

    public KillauraSwingPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleSwing(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        s.lastSwingMs = now;
    }

    public void handleAttack(Player player, Entity target, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("killaura_swing_packet")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("killaura_swing_packet");
        long swingWindowMs = sec != null ? sec.getLong("swing_window_ms", DEFAULT_SWING_WINDOW_MS) : DEFAULT_SWING_WINDOW_MS;
        double fovThr      = sec != null ? sec.getDouble("max_fov_deg",   DEFAULT_FOV_DEG)         : DEFAULT_FOV_DEG;

        long sinceSwing = now - s.lastSwingMs;

        if (s.lastSwingMs == 0 || sinceSwing > swingWindowMs) {
            sink.flag(new Violation(player, "killaura_no_swing_packet",
                ViolationLevel.HIGH,
                String.format("sinceSwing=%dms (>%dms or never)", sinceSwing, swingWindowMs)));
            return;
        }

        org.bukkit.Location tloc = target.getLocation();
        double dx = tloc.getX() - s.lastX;
        double dz = tloc.getZ() - s.lastZ;
        if (dx == 0 && dz == 0) return;

        double yawToTarget = Math.toDegrees(Math.atan2(-dx, dz));
        double diff = Math.abs(normalizeYaw(s.lastYaw - (float) yawToTarget));

        if (diff > fovThr) {
            sink.flag(new Violation(player, "killaura_fov_packet",
                ViolationLevel.HIGH,
                String.format("yawDiff=%.1f° (target out of FOV >%.1f°)", diff, fovThr)));
        }
    }

    private static double normalizeYaw(double y) {
        y = y % 360.0;
        if (y >= 180.0)  y -= 360.0;
        if (y < -180.0)  y += 360.0;
        return Math.abs(y);
    }
}
