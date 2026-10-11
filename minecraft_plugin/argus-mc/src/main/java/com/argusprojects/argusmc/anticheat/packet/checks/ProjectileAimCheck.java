package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Location;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.entity.Projectile;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.ProjectileHitEvent;

public final class ProjectileAimCheck {

    private final ArgusPlugin plugin;

    public ProjectileAimCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleHit(Player shooter, Projectile projectile, PacketDataStore.State s,
                          ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("projectile_aim")) return;
        if (projectile == null || shooter == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("projectile_aim");
        double minDistFlag = sec != null ? sec.getDouble("min_distance", 25.0) : 25.0;
        double maxAngleDeg = sec != null ? sec.getDouble("max_angle_deg", 1.5) : 1.5;

        Location origin = shooter.getEyeLocation();
        Location hit    = projectile.getLocation();

        double dist = origin.distance(hit);
        if (dist < minDistFlag) return;

        org.bukkit.util.Vector vel = projectile.getVelocity();
        if (vel.lengthSquared() < 0.01) return;

        org.bukkit.util.Vector toTarget = hit.toVector().subtract(origin.toVector()).normalize();
        org.bukkit.util.Vector velN = vel.clone().normalize();
        double dot = Math.max(-1.0, Math.min(1.0, velN.dot(toTarget)));
        double angleDeg = Math.toDegrees(Math.acos(dot));

        if (angleDeg <= maxAngleDeg) {
            sink.flag(new Violation(shooter, "projectile_aim_packet",
                ViolationLevel.HIGH,
                String.format("dist=%.1f angle=%.2f° (<= %.2f°)", dist, angleDeg, maxAngleDeg)));
        }
    }
}
