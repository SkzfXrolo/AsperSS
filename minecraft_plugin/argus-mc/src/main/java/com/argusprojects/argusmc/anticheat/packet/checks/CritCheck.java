package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.entity.Player;
import org.bukkit.event.entity.EntityDamageByEntityEvent;

public final class CritCheck {

    private final ArgusPlugin plugin;

    public CritCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleDamage(Player player, PacketDataStore.State s,
                             EntityDamageByEntityEvent event, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("crit")) return;
        if (player.getGameMode() == GameMode.CREATIVE || player.getGameMode() == GameMode.SPECTATOR) return;

        boolean isCrit;
        try {
            isCrit = event.isCritical();
        } catch (Throwable t) {
            return;
        }
        if (!isCrit) return;

        if (player.getFallDistance() > 0.0f && !player.isOnGround()) {
            return;
        }
        if (player.isInsideVehicle()) return;

        sink.flag(new Violation(player, "crit_packet",
            ViolationLevel.HIGH,
            String.format("crit con onGround=%s fall=%.2f", player.isOnGround(), player.getFallDistance())));
    }
}
