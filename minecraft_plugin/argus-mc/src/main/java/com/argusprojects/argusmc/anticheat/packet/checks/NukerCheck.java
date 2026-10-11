package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class NukerCheck {

    private final ArgusPlugin plugin;

    public NukerCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleFinishDigging(Player player, PacketDataStore.State s, long now,
                                    org.bukkit.Material blockType, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("nuker")) return;
        if (player.getGameMode() == GameMode.CREATIVE) return;
        if (player.getGameMode() == GameMode.SPECTATOR) return;
        if (blockType == null) return;
        try {
            if (blockType.getHardness() < 0.05f) return;
        } catch (Throwable t) {
            return;
        }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("nuker");
        long windowMs = sec != null ? sec.getLong("window_ms", 60L) : 60L;
        int  midAt    = sec != null ? sec.getInt("min_breaks_mid", 3) : 3;
        int  highAt   = sec != null ? sec.getInt("min_breaks_high", 5) : 5;

        int recent = s.recentBreaksWithin(windowMs, now);
        if (recent >= highAt) {
            sink.flag(new Violation(player, "nuker_packet",
                ViolationLevel.HIGH,
                String.format("breaks=%d/%dms (>=%d)", recent, windowMs, highAt)));
        } else if (recent >= midAt) {
            sink.flag(new Violation(player, "nuker_packet",
                ViolationLevel.MID,
                String.format("breaks=%d/%dms (>=%d)", recent, windowMs, midAt)));
        }
    }
}
