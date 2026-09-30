package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

import java.util.Iterator;

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
