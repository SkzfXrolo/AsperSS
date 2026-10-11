package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class FastEatCheck {

    private final ArgusPlugin plugin;

    public FastEatCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleEatFinish(Player player, PacketDataStore.State s,
                                long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("fasteat")) return;
        if (s.useItemStartMs == 0L) return;
        long elapsed = now - s.useItemStartMs;
        s.lastEatFinishMs = now;
        s.useItemStartMs  = 0L;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("fasteat");
        long minEatMs   = sec != null ? sec.getLong("min_eat_ms", 1500L) : 1500L;
        long extremeMs  = sec != null ? sec.getLong("extreme_ms", 800L) : 800L;

        if (elapsed < extremeMs) {
            sink.flag(new Violation(player, "fasteat_packet",
                ViolationLevel.HIGH,
                "ate in " + elapsed + "ms (vanilla=1610ms)"));
        } else if (elapsed < minEatMs) {
            sink.flag(new Violation(player, "fasteat_packet",
                ViolationLevel.MID,
                "ate in " + elapsed + "ms"));
        }
    }
}
