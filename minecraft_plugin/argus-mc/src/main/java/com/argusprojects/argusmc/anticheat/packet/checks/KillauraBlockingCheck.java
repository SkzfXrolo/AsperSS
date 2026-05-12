package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — KillauraBlockingCheck.
 *
 * <p>Detecta cuando un jugador ataca a otra entidad mientras esta bloqueando
 * con un escudo (1.9+) o sword (pre-1.9 — handled by isBlocking()). En
 * vanilla NO se puede dar un swing/ataque mientras tenes el shield activo
 * (block consume el primer slot de input). Los killauras "fake-block" reciben
 * el daño compensado por el bloqueo sin perder DPS.
 *
 * <p>Bukkit expone {@link Player#isBlocking()} que devuelve true para shield
 * activo o sword raised (legacy). Si esto es true en el momento del attack
 * packet, es trampa.
 */
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
