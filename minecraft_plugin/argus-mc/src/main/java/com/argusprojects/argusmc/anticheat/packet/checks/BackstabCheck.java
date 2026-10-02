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
import org.bukkit.util.Vector;

public final class BackstabCheck {

    private final ArgusPlugin plugin;

    public BackstabCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player attacker, Entity target, PacketDataStore.State s,
                             ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("backstab")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("backstab");
        double maxFov       = sec != null ? sec.getDouble("max_fov_deg", 100.0) : 100.0;
        double extremeFov   = sec != null ? sec.getDouble("extreme_fov_deg", 140.0) : 140.0;

        Location eye = attacker.getEyeLocation();
        Vector look  = eye.getDirection();
        Vector toTarget = target.getLocation().add(0, 1.0, 0).toVector().subtract(eye.toVector());
        if (toTarget.lengthSquared() < 0.001) return;
        toTarget = toTarget.normalize();

        double dot = Math.max(-1.0, Math.min(1.0, look.dot(toTarget)));
        double angleDeg = Math.toDegrees(Math.acos(dot));

        if (angleDeg >= extremeFov) {
            sink.flag(new Violation(attacker, "backstab_packet",
                ViolationLevel.CRITICAL,
                String.format("attack FOV %.1f° (>=%.0f°)", angleDeg, extremeFov)));
        } else if (angleDeg >= maxFov) {
            sink.flag(new Violation(attacker, "backstab_packet",
                ViolationLevel.HIGH,
                String.format("attack FOV %.1f° (>=%.0f°)", angleDeg, maxFov)));
        }
    }

    /**
     * FOV con rotacion de paquetes: mejor angulo entre la rotacion previa y la siguiente al golpe,
     * descontando el tamano angular del objetivo + su movimiento por lag. A menos de 1 bloque
     * horizontal el angulo no significa nada (el otro esta encima/pegado) y no se evalua.
     */
    public void evaluate(Player attacker, Entity target, PacketDataStore.State s,
                         float yaw0, float pitch0, float yaw1, float pitch1, double lag, ViolationSink sink) {
        org.bukkit.util.BoundingBox bb = target.getBoundingBox();
        double ex = s.lastX, ey = s.lastY + (attacker.isSneaking() ? 1.27 : 1.62), ez = s.lastZ;
        double tx = bb.getCenterX() - ex, ty = bb.getCenterY() - ey, tz = bb.getCenterZ() - ez;
        double hd = Math.hypot(tx, tz);
        if (hd < 1.0) return;
        double radius = Math.toDegrees(Math.atan((bb.getWidthX() / 2 + lag) / hd));
        double len = Math.sqrt(tx * tx + ty * ty + tz * tz);
        double yawTo = Math.toDegrees(Math.atan2(-tx, tz));
        double ang3d = Math.min(angle3d(yaw0, pitch0, tx / len, ty / len, tz / len), angle3d(yaw1, pitch1, tx / len, ty / len, tz / len)) - radius;
        double yawDiff = Math.min(yawDiff(yaw0, yawTo), yawDiff(yaw1, yawTo)) - radius;

        if (plugin.getAnticheatConfig().isCheckEnabled("backstab")) {
            ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("backstab");
            double maxFov     = sec != null ? sec.getDouble("max_fov_deg", 100.0) : 100.0;
            double extremeFov = sec != null ? sec.getDouble("extreme_fov_deg", 140.0) : 140.0;
            if (ang3d >= extremeFov) {
                sink.flag(new Violation(attacker, "backstab_packet", ViolationLevel.CRITICAL,
                    String.format("pego fuera de la vista: %.0f°", ang3d)));
            } else if (ang3d >= maxFov) {
                sink.flag(new Violation(attacker, "backstab_packet", ViolationLevel.HIGH,
                    String.format("pego fuera de la vista: %.0f°", ang3d)));
            }
        }
        if (plugin.getAnticheatConfig().isCheckEnabled("killaura_swing_packet")) {
            ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("killaura_swing_packet");
            double fovThr = sec != null ? sec.getDouble("max_fov_deg", 90.0) : 90.0;
            if (yawDiff > fovThr) {
                sink.flag(new Violation(attacker, "killaura_fov_packet", ViolationLevel.HIGH,
                    String.format("objetivo a %.0f° de la mira", yawDiff)));
            }
        }
    }

    private static double angle3d(float yawDeg, float pitchDeg, double tx, double ty, double tz) {
        double yaw = Math.toRadians(yawDeg), pitch = Math.toRadians(pitchDeg);
        double lx = -Math.sin(yaw) * Math.cos(pitch), ly = -Math.sin(pitch), lz = Math.cos(yaw) * Math.cos(pitch);
        return Math.toDegrees(Math.acos(Math.max(-1.0, Math.min(1.0, lx * tx + ly * ty + lz * tz))));
    }

    private static double yawDiff(float yaw, double yawTo) {
        double d = (yaw - yawTo) % 360.0;
        if (d >= 180.0) d -= 360.0;
        if (d < -180.0) d += 360.0;
        return Math.abs(d);
    }
}
