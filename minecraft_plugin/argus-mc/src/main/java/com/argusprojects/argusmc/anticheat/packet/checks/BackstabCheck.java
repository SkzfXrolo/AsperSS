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

/**
 * Pack 48 round2 — BackstabCheck.
 *
 * <p>Killaura "BackTrack" / "Backstab" hace que el atacante hitee a entidades
 * que estan detras suyo (FOV > 100 grados) sin girarse legitimamente. Tambien
 * detecta el "TargetSwap" donde el cheat va rotando entre multiples objetivos
 * 360° en cada tick.
 *
 * <p>Heuristica: si el angulo entre la mirada del atacante y el vector
 * atacante→target es &gt; max_fov_deg al momento exacto del attack, el hit
 * es ilegitimo (vanilla cap esta cerca de 90).
 */
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
}
