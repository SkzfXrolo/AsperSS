package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class InvMovePacketCheck {

    private final ArgusPlugin plugin;

    public InvMovePacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleClickWindow(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("inv_move_packet")) return;
        if (!s.inventoryOpen) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("inv_move_packet");
        long graceMs       = sec != null ? sec.getLong("grace_ms",         300L) : 300L;
        long staleMoveMs   = sec != null ? sec.getLong("stale_move_ms",  1_000L) : 1_000L;

        if (now - s.inventoryOpenSinceMs < graceMs) return;

        if (s.lastMoveMs > s.inventoryOpenSinceMs + graceMs
            && now - s.lastMoveMs < staleMoveMs) {
            sink.flag(new Violation(player, "inv_move_packet",
                ViolationLevel.MID,
                String.format("clickWindow during movement (lastMove %dms ago, invOpen %dms)",
                    now - s.lastMoveMs, now - s.inventoryOpenSinceMs)));
        }
    }
}
