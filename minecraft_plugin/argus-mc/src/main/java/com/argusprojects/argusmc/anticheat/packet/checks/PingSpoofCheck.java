package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class PingSpoofCheck {

    private final ArgusPlugin plugin;

    public PingSpoofCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleKeepAliveResponse(Player player, PacketDataStore.State s, long rttMs, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("ping_spoof")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("ping_spoof");
        long warmupMs       = sec != null ? sec.getLong("warmup_ms",       5_000L) : 5_000L;
        long minRttMs       = sec != null ? sec.getLong("min_rtt_ms",      3L)     : 3L;
        long extremeRttMs   = sec != null ? sec.getLong("extreme_rtt_ms", 5_000L)  : 5_000L;
        int  lowRttStreak   = sec != null ? sec.getInt("low_rtt_streak",  4)      : 4;
        int  lanPingCutoff  = sec != null ? sec.getInt("lan_ping_cutoff_ms", 12)    : 12;

        if (System.currentTimeMillis() - s.joinMs < warmupMs) return;

        int bukkitPing = safePing(player);
        if (bukkitPing >= 0 && bukkitPing <= lanPingCutoff) {
            s.pingSpoofLowRttStreak = 0;
            return;
        }

        if (rttMs >= 0 && rttMs < minRttMs) {
            s.pingSpoofLowRttStreak++;
            if (s.pingSpoofLowRttStreak < lowRttStreak) return;
            sink.flag(new Violation(player, "ping_spoof_packet",
                ViolationLevel.LOW,
                String.format("rtt=%dms (sustained <%dms)", rttMs, minRttMs)));
            s.pingSpoofLowRttStreak = 0;
        } else if (rttMs > extremeRttMs) {
            s.pingSpoofLowRttStreak = 0;
            sink.flag(new Violation(player, "ping_spoof_packet",
                ViolationLevel.LOW,
                String.format("rtt=%dms (extreme lag or spoof)", rttMs)));
        } else {
            s.pingSpoofLowRttStreak = 0;
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
