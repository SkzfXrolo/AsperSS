package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class RegenCheck {

    private final ArgusPlugin plugin;

    public RegenCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleHealthChange(Player player, PacketDataStore.State s,
                                   double newHealth, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("regen")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("regen");
        double maxRegenPerSec = sec != null ? sec.getDouble("max_hp_per_sec", 2.2) : 2.2;
        long   minInterval    = sec != null ? sec.getLong("min_interval_ms", 450L) : 450L;
        int    consecHigh     = sec != null ? sec.getInt("consec_high", 3) : 3;

        double delta = newHealth - s.lastHealth;
        long   dt    = now - s.lastHealthChangeMs;

        s.lastHealth = newHealth;
        s.lastHealthChangeMs = now;

        if (delta <= 0) return;
        if (dt <= 0) return;

        double hpPerSec = delta * 1000.0 / dt;
        if (hpPerSec > maxRegenPerSec || dt < minInterval) {
            s.regenAnomaliesInWindow++;
            if (s.regenAnomaliesInWindow >= consecHigh) {
                sink.flag(new Violation(player, "regen_packet",
                    ViolationLevel.HIGH,
                    String.format("regen %.2fhp/s dt=%dms x%d",
                        hpPerSec, dt, s.regenAnomaliesInWindow)));
                s.regenAnomaliesInWindow = 0;
            } else {
                sink.flag(new Violation(player, "regen_packet",
                    ViolationLevel.MID,
                    String.format("regen %.2fhp/s dt=%dms", hpPerSec, dt)));
            }
        } else {
            s.regenAnomaliesInWindow = 0;
        }
    }
}
