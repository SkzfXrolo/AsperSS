package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;

public final class Reach3DCheck {

    private final ArgusPlugin plugin;

    public Reach3DCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target, PacketDataStore.State s,
                             double lagAllowance, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("reach3d")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("reach3d");
        double maxSurvival = sec != null ? sec.getDouble("max_survival", 3.05) : 3.05;
        double maxCreative = sec != null ? sec.getDouble("max_creative", 5.05) : 5.05;
        double extreme     = sec != null ? sec.getDouble("extreme", 4.5) : 4.5;
        int    consecHigh  = sec != null ? sec.getInt("consec_high", 3) : 3;

        BoundingBox bb;
        try { bb = target.getBoundingBox(); } catch (Throwable ignored) { return; }
        // Posicion de los paquetes: la de Bukkit va atrasada respecto de lo que el cliente ya mando.
        Vector eye = (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) ? player.getEyeLocation().toVector()
            : new Vector(s.lastX, s.lastY + (player.isSneaking() ? 1.27 : 1.62), s.lastZ);

        double cx = clamp(eye.getX(), bb.getMinX(), bb.getMaxX());
        double cy = clamp(eye.getY(), bb.getMinY(), bb.getMaxY());
        double cz = clamp(eye.getZ(), bb.getMinZ(), bb.getMaxZ());
        double dx = eye.getX() - cx;
        double dy = eye.getY() - cy;
        double dz = eye.getZ() - cz;
        double dist = Math.sqrt(dx*dx + dy*dy + dz*dz) - lagAllowance;

        double cap = player.getGameMode() == GameMode.CREATIVE ? maxCreative : maxSurvival;
        if (dist > extreme) {
            sink.flag(new Violation(player, "reach3d_packet",
                ViolationLevel.HIGH,
                String.format("3D-bbox-reach=%.3f > extreme=%.2f", dist, extreme)));
            s.reach3dConsec = 0;
        } else if (dist > cap) {
            s.reach3dConsec++;
            if (s.reach3dConsec >= consecHigh) {
                sink.flag(new Violation(player, "reach3d_packet",
                    ViolationLevel.HIGH,
                    String.format("3D-bbox-reach=%.3f > cap=%.2f x%d", dist, cap, s.reach3dConsec)));
                s.reach3dConsec = 0;
            } else {
                sink.flag(new Violation(player, "reach3d_packet",
                    ViolationLevel.MID,
                    String.format("3D-bbox-reach=%.3f > cap=%.2f", dist, cap)));
            }
        } else {
            s.reach3dConsec = 0;
        }
    }

    private static double clamp(double v, double lo, double hi) {
        return Math.max(lo, Math.min(hi, v));
    }
}
