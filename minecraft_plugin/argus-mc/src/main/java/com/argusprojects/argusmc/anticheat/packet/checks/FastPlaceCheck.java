package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class FastPlaceCheck {

    private final ArgusPlugin plugin;

    public FastPlaceCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBlockPlacement(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("fast_place")) return;
        if (player.getGameMode() == GameMode.CREATIVE) return;

        s.pushPlace(now);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("fast_place");
        int maxPerSec  = sec != null ? sec.getInt("max_per_sec",  9)  : 9;
        int maxPerSec2 = sec != null ? sec.getInt("max_per_sec2", 14) : 14;
        int maxPerSec3 = sec != null ? sec.getInt("max_per_sec3", 22) : 22;

        int recent = s.recentPlacesWithin(1_000L, now);
        if (recent >= maxPerSec3) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.HIGH,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec3)));
        } else if (recent >= maxPerSec2) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.MID,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec2)));
        } else if (recent >= maxPerSec) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.LOW,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec)));
        }
    }
}
