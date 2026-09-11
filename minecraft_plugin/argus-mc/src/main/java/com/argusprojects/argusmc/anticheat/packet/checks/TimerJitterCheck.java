package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class TimerJitterCheck {

    private final ArgusPlugin plugin;

    public TimerJitterCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("timer_jitter")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "timer_jitter")) return;

        if (safePing(player) >= 0 && safePing(player) <= 15) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("timer_jitter");
        int    windowSize = sec != null ? sec.getInt("window_size", 20) : 20;
        double minStdMs   = sec != null ? sec.getDouble("min_stddev_ms", 5.0) : 5.0;
        double maxStdMs   = sec != null ? sec.getDouble("max_stddev_ms", 35.0) : 35.0;
        double minAvgMs   = sec != null ? sec.getDouble("min_avg_ms", 35.0) : 35.0;

        long[] arr;
        synchronized (s) {
            if (s.moveTimestamps.size() < windowSize) return;
            arr = new long[s.moveTimestamps.size()];
            int i = 0;
            for (Long t : s.moveTimestamps) arr[i++] = t;
        }

        double sum = 0, sum2 = 0;
        int n = arr.length - 1;
        if (n < 5) return;
        for (int i = 1; i < arr.length; i++) {
            long dt = arr[i] - arr[i - 1];
            sum  += dt;
            sum2 += (double) dt * dt;
        }
        double mean = sum / n;
        double variance = (sum2 / n) - (mean * mean);
        if (variance < 0) variance = 0;
        double stddev = Math.sqrt(variance);

        if (mean < minAvgMs && stddev < minStdMs) {
            sink.flag(new Violation(player, "timer_jitter_packet",
                ViolationLevel.HIGH,
                String.format("timer ON avg=%.1fms stddev=%.1fms (n=%d)", mean, stddev, n)));
        } else if (stddev > maxStdMs && mean < 60) {
            sink.flag(new Violation(player, "timer_jitter_packet",
                ViolationLevel.LOW,
                String.format("timer JITTER avg=%.1fms stddev=%.1fms", mean, stddev)));
        }
    }

    private static int safePing(Player player) {
        try {
            return player.getPing();
        } catch (Throwable t) {
            return -1;
        }
    }
}
