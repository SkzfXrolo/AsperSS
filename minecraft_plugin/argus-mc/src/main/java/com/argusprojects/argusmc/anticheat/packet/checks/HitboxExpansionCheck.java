package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Location;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.util.BoundingBox;

public final class HitboxExpansionCheck {

    private final ArgusPlugin plugin;

    public HitboxExpansionCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player attacker, Entity target, PacketDataStore.State s,
                             double lagComp, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("hitbox_expansion")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("hitbox_expansion");
        double margin       = sec != null ? sec.getDouble("max_margin", 0.20) : 0.20;
        double extremeMargin= sec != null ? sec.getDouble("extreme_margin", 0.50) : 0.50;

        Location eye = attacker.getEyeLocation();
        if (!(s.lastX == 0 && s.lastY == 0 && s.lastZ == 0)) {
            eye = new Location(eye.getWorld(), s.lastX, s.lastY + (attacker.isSneaking() ? 1.27 : 1.62), s.lastZ);
        }
        BoundingBox bb;
        try {
            bb = target.getBoundingBox();
        } catch (Throwable t) {
            return;
        }

        double cx = clamp(eye.getX(), bb.getMinX(), bb.getMaxX());
        double cy = clamp(eye.getY(), bb.getMinY(), bb.getMaxY());
        double cz = clamp(eye.getZ(), bb.getMinZ(), bb.getMaxZ());
        double dx = eye.getX() - cx;
        double dy = eye.getY() - cy;
        double dz = eye.getZ() - cz;

        double distToBox = Math.sqrt(dx * dx + dy * dy + dz * dz);

        double reachMax = 3.0;
        // Igual que reach_packet: el objetivo pudo moverse mientras viajaba el paquete (ping + interpolacion).
        double overflow = distToBox - lagComp - reachMax;
        if (overflow >= extremeMargin) {
            sink.flag(new Violation(attacker, "hitbox_expansion_packet",
                ViolationLevel.HIGH,
                String.format("dist_bb=%.2f lag=%.2f overflow=%.2f", distToBox, lagComp, overflow)));
        } else if (overflow >= margin) {
            sink.flag(new Violation(attacker, "hitbox_expansion_packet",
                ViolationLevel.MID,
                String.format("dist_bb=%.2f lag=%.2f overflow=%.2f", distToBox, lagComp, overflow)));
        }
    }

    private static double clamp(double v, double min, double max) {
        return Math.max(min, Math.min(max, v));
    }
}
