package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 47 — PingSpoofCheck.
 *
 * <p>El server envia KeepAlive con un ID y espera la respuesta del cliente.
 * El intervalo entre send y receive es el RTT real (ping). PingSpoof manipula
 * este RTT para que el server crea que tienes mas lag del real (lo usa con
 * Reach/Killaura para ganar "tickrate buffer").
 *
 * <p>Detectamos:
 * <ul>
 *   <li>RTT &lt; 5ms: imposible para cliente real (incluso localhost queda en ~10ms).
 *       Probablemente el cliente esta respondiendo con cache (NPC client).</li>
 *   <li>RTT con gran varianza repentina (no implementado aca; ruido natural cubre eso).</li>
 *   <li>RTT &gt; 2000ms sostenido: laggy o spoof. LOW alert, no kick.</li>
 * </ul>
 */
public final class PingSpoofCheck {

    private final ArgusPlugin plugin;

    public PingSpoofCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleKeepAliveResponse(Player player, PacketDataStore.State s, long rttMs, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("ping_spoof")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("ping_spoof");
        long warmupMs      = sec != null ? sec.getLong("warmup_ms",       5_000L) : 5_000L;
        long minRttMs      = sec != null ? sec.getLong("min_rtt_ms",      3L)     : 3L;
        long extremeRttMs  = sec != null ? sec.getLong("extreme_rtt_ms", 5_000L)  : 5_000L;

        if (System.currentTimeMillis() - s.joinMs < warmupMs) return;

        if (rttMs >= 0 && rttMs < minRttMs) {
            sink.flag(new Violation(player, "ping_spoof_packet",
                ViolationLevel.MID,
                String.format("rtt=%dms (impossible <%dms)", rttMs, minRttMs)));
        } else if (rttMs > extremeRttMs) {
            sink.flag(new Violation(player, "ping_spoof_packet",
                ViolationLevel.LOW,
                String.format("rtt=%dms (extreme lag or spoof)", rttMs)));
        }
    }
}
