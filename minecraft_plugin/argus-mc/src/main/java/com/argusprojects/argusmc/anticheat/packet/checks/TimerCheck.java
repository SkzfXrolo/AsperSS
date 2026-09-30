package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class TimerCheck {

    private static final long DEFAULT_WINDOW_MS = 1_500L;
    private static final long DEFAULT_IDEAL_INTERVAL_MS = 50L;
    private static final long DEFAULT_TOLERANCE_MS = 280L;
    private static final long DEFAULT_HIGH_THRESHOLD_MS = 550L;
    private static final int  DEFAULT_MIN_PACKETS = 12;
    private static final double DEFAULT_MIN_RATIO = 1.30;

    private final ArgusPlugin plugin;

    public TimerCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("timer")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("timer");
        long windowMs       = sec != null ? sec.getLong("window_ms",        DEFAULT_WINDOW_MS)        : DEFAULT_WINDOW_MS;
        long idealMs        = sec != null ? sec.getLong("ideal_interval_ms", DEFAULT_IDEAL_INTERVAL_MS) : DEFAULT_IDEAL_INTERVAL_MS;
        long toleranceMs    = sec != null ? sec.getLong("tolerance_ms",      DEFAULT_TOLERANCE_MS)    : DEFAULT_TOLERANCE_MS;
        long highBalanceMs  = sec != null ? sec.getLong("high_balance_ms",  DEFAULT_HIGH_THRESHOLD_MS): DEFAULT_HIGH_THRESHOLD_MS;
        int  minPackets     = sec != null ? sec.getInt("min_packets",       DEFAULT_MIN_PACKETS)      : DEFAULT_MIN_PACKETS;
        long warmupMs       = sec != null ? sec.getLong("warmup_ms",        2_000L)                   : 2_000L;
        long bucketMs       = sec != null ? sec.getLong("bucket_ms",        25L)                      : 25L;
        long flagCooldownMs = sec != null ? sec.getLong("flag_cooldown_ms", 3_000L)                   : 3_000L;
        int  lanPingCutoff  = sec != null ? sec.getInt("lan_ping_cutoff_ms", 20)                     : 20;
        double minRatio     = sec != null ? sec.getDouble("min_ratio", DEFAULT_MIN_RATIO)              : DEFAULT_MIN_RATIO;

        if (now - s.joinMs < warmupMs) return;
        if (s.teleporting && now < s.teleportUntilMs) return;
        if (s.teleporting && now >= s.teleportUntilMs) {
            s.teleporting = false;
        }

        int ping = safePing(player);
        if (ping >= 0 && ping <= lanPingCutoff) return;

        int count;
        long oldest;
        synchronized (s) {
            long cutoff = now - windowMs;
            count = 0;
            oldest = now;
            long prevBucket = -1L;
            for (Long t : s.moveTimestamps) {
                if (t < cutoff) continue;
                if (t < oldest) oldest = t;
                long bucket = t / bucketMs;
                if (bucket != prevBucket) {
                    count++;
                    prevBucket = bucket;
                }
            }
        }
        if (count < minPackets) return;

        long expectedMs = count * idealMs;
        long actualMs   = Math.max(1L, now - oldest);
        long balance    = actualMs - expectedMs;

        if (balance >= -toleranceMs) return;

        double ratio = expectedMs > 0 ? (double) expectedMs / actualMs : 1.0;
        if (ratio < minRatio) return;

        if (now - s.lastTimerFlagMs < flagCooldownMs) return;

        ViolationLevel lvl;
        if (balance < -highBalanceMs && ratio >= minRatio + 0.35) {
            lvl = ViolationLevel.HIGH;
        } else if (ratio >= minRatio + 0.15) {
            lvl = ViolationLevel.MID;
        } else {
            lvl = ViolationLevel.LOW;
        }

        sink.flag(new Violation(player, "timer_packet",
            lvl,
            String.format("packets=%d balance=%dms ratio=%.2fx", count, balance, ratio)));
        s.lastTimerFlagMs = now;
    }

    private static int safePing(Player player) {
        try {
            return player.getPing();
        } catch (Throwable t) {
            return -1;
        }
    }
}
