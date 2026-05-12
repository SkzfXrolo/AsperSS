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

/**
 * Pack 48 round2 — ProjectileAimCheck.
 *
 * <p>Cuando un proyectil (arrow, snowball, trident) impacta a un jugador
 * desde una distancia grande con un angulo "perfecto" (delta entre la
 * direccion del proyectil al target y la direccion de viaje del proyectil
 * es minimo), es bot-aim.
 *
 * <p>Se invoca desde {@link ProjectileHitEvent} y desde
 * {@link EntityDamageByEntityEvent} en el bridge Bukkit. La logica usa
 * la velocidad del proyectil al momento del hit para inferir el aim
 * inicial — si el shooter tenia gran skill (alta distancia, target en
 * movimiento) flagea.
 */
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

        // Vector velocidad del proyectil al hit (gravity-affected pero indicativa).
        org.bukkit.util.Vector vel = projectile.getVelocity();
        if (vel.lengthSquared() < 0.01) return;

        // Vector linea recta origen->target.
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
