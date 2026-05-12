package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

import java.util.Iterator;

/**
 * Pack 48 round 3 — KillauraRotationCheck.
 *
 * <p>Detecta patrones de rotación inhumanos: cambio mayor a
 * {@code max_yaw_step_deg} (default 180°) en menos de
 * {@code min_step_interval_ms} (default 50ms) entre dos rotation
 * packets consecutivos.
 *
 * <p>Las killauras "snap-aim" mueven la cámara directo al target sin
 * pasar por estados intermedios. Un humano hace 180° en mínimo ~150ms
 * con varios packets intermedios.
 */
public final class KillauraRotationCheck {

    private final ArgusPlugin plugin;

    public KillauraRotationCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s,
                               float newYaw, float newPitch, long now,
                               ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("killaura_rotation")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("killaura_rotation");
        double maxYawStep    = sec != null ? sec.getDouble("max_yaw_step_deg", 170.0) : 170.0;
        long   minStepInterval = sec != null ? sec.getLong("min_step_interval_ms", 50L) : 50L;
        int    requiredHits  = sec != null ? sec.getInt("required_hits", 2) : 2;

        synchronized (s) {
            if (s.recentRotations.size() < 2) return;
            // Tomar los dos ultimos samples y comparar.
            Iterator<PacketDataStore.RotationSample> it = s.recentRotations.descendingIterator();
            PacketDataStore.RotationSample last = it.next();
            if (!it.hasNext()) return;
            PacketDataStore.RotationSample prev = it.next();

            long dt = last.tsMs - prev.tsMs;
            if (dt <= 0 || dt > 1000L) return;

            double dyaw = Math.abs(angleDelta(last.yaw, prev.yaw));
            if (dyaw >= maxYawStep && dt <= minStepInterval) {
                if (s.recentAttacksWithin(500L, now) >= requiredHits) {
                    sink.flag(new Violation(player, "killaura_rotation_packet",
                        ViolationLevel.HIGH,
                        String.format("snap yaw=%.1f° dt=%dms hits=%d",
                            dyaw, dt, s.recentAttacksWithin(500L, now))));
                }
            }
        }
    }

    private static double angleDelta(float a, float b) {
        double d = ((a - b + 540.0) % 360.0) - 180.0;
        return d;
    }
}
