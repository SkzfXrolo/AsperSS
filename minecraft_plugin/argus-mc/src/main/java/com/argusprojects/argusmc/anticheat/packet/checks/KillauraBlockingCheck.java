package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

public final class KillauraBlockingCheck {

    private final ArgusPlugin plugin;

    public KillauraBlockingCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target, PacketDataStore.State s,
                             long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("killaura_blocking")) return;
        if (target == null) return;
        try {
            if (player.isBlocking()) {
                sink.flag(new Violation(player, "killaura_blocking_packet",
                    ViolationLevel.HIGH,
                    "attack while shield/blocking active"));
            }
        } catch (Throwable ignored) {
        }
    }
}
