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

public final class ReachPacketCheck {

    private final ArgusPlugin plugin;

    public ReachPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target,
                             PacketDataStore.State s, double lagAllowance,
                             ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("reach_packet")) return;
        if (target == null) return;
        if (target.getUniqueId().equals(player.getUniqueId())) return;

        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE) {
            return;
        }
        if (gm == GameMode.SPECTATOR) return;

        double ax = s.lastX;
        double ay = s.lastY + 1.62;
        double az = s.lastZ;
        // Vanilla mide 3.0 desde el ojo hasta el punto mas cercano de la hitbox, no hasta el centro.
        org.bukkit.util.BoundingBox bb;
        try { bb = target.getBoundingBox(); } catch (Throwable ignored) { return; }
        double cx = Math.max(bb.getMinX(), Math.min(bb.getMaxX(), ax));
        double cy = Math.max(bb.getMinY(), Math.min(bb.getMaxY(), ay));
        double cz = Math.max(bb.getMinZ(), Math.min(bb.getMaxZ(), az));
        double rawDist = Math.sqrt((ax - cx) * (ax - cx) + (ay - cy) * (ay - cy) + (az - cz) * (az - cz));
        double dist = rawDist - lagAllowance;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("reach_packet");
        double midThr      = sec != null ? sec.getDouble("dist_mid",      3.3) : 3.3;
        double highThr     = sec != null ? sec.getDouble("dist_high",     3.6) : 3.6;
        double criticalThr = sec != null ? sec.getDouble("dist_critical", 4.5) : 4.5;

        if (dist > criticalThr) {
            sink.flag(new Violation(player, "reach_packet",
                ViolationLevel.CRITICAL,
                String.format("dist=%.2f (hitbox %.2f - lag %.2f) target=%s", dist, rawDist, lagAllowance, target.getType().name().toLowerCase())));
        } else if (dist > highThr) {
            sink.flag(new Violation(player, "reach_packet",
                ViolationLevel.HIGH,
                String.format("dist=%.2f (hitbox %.2f - lag %.2f) target=%s", dist, rawDist, lagAllowance, target.getType().name().toLowerCase())));
        } else if (dist > midThr) {
            sink.flag(new Violation(player, "reach_packet",
                ViolationLevel.MID,
                String.format("dist=%.2f (hitbox %.2f - lag %.2f) target=%s", dist, rawDist, lagAllowance, target.getType().name().toLowerCase())));
        }
    }
}
