package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.entity.Player;
import org.bukkit.event.entity.EntityDamageByEntityEvent;

/**
 * Pack 48 round2 — CritCheck.
 *
 * <p>Crits vanilla exigen que el atacante este cayendo (fall distance &gt; 0,
 * no on-ground, no en escalera/agua, no montado, no sprint/blind). Los cheats
 * "AutoCrit" / "CritHack" hacen que TODOS los hits sean criticos sin saltar.
 *
 * <p>Se invoca desde {@link EntityDamageByEntityEvent} en el bridge Bukkit.
 * Si {@code event.isCritical()} es true y el jugador esta on-ground sin
 * fall distance, es trampa.
 */
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
            return; // API no presente
        }
        if (!isCrit) return;

        // Vanilla: crit valido solo si fallDistance > 0 y no on-ground.
        if (player.getFallDistance() > 0.0f && !player.isOnGround()) {
            return; // legitimo
        }
        if (player.isInsideVehicle()) return;

        sink.flag(new Violation(player, "crit_packet",
            ViolationLevel.HIGH,
            String.format("crit con onGround=%s fall=%.2f", player.isOnGround(), player.getFallDistance())));
    }
}
