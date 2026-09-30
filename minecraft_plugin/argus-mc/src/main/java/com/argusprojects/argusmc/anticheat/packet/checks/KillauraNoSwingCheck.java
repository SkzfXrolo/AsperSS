package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

public final class KillauraNoSwingCheck {

    private final ArgusPlugin plugin;

    public KillauraNoSwingCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target, PacketDataStore.State s,
                             long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("killaura_noswing")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("killaura_noswing");
        long maxSwingLag = sec != null ? sec.getLong("max_swing_lag_ms", 100L) : 100L;
        int  consecMid   = sec != null ? sec.getInt("consec_mid", 3) : 3;
        int  consecHigh  = sec != null ? sec.getInt("consec_high", 5) : 5;

        long sinceSwing = s.lastSwingMs == 0 ? Long.MAX_VALUE : (now - s.lastSwingMs);
        if (sinceSwing <= maxSwingLag) {
            s.noSwingConsec = 0;
            return;
        }
        s.noSwingConsec++;
        int n = s.noSwingConsec;
        if (n >= consecHigh) {
            sink.flag(new Violation(player, "killaura_noswing_packet",
                ViolationLevel.HIGH,
                "attack sin swing x" + n + " (lag=" + sinceSwing + "ms)"));
            s.noSwingConsec = 0;
        } else if (n >= consecMid) {
            sink.flag(new Violation(player, "killaura_noswing_packet",
                ViolationLevel.MID,
                "attack sin swing x" + n + " (lag=" + sinceSwing + "ms)"));
        }
    }
}
