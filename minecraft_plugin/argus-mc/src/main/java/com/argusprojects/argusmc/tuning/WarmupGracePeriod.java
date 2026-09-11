package com.argusprojects.argusmc.tuning;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — Periodo de gracia tras join / teleport.
 *
 * <p>Cuando un jugador entra al server o teleporta, el cliente recibe
 * un chunk-batch y un PlayerPosition al mismo tiempo. Los timestamps
 * de Netty no coinciden con el "primer tick simulado" del cliente, lo
 * cual produce ráfagas de violations falsas durante los primeros segundos.
 *
 * <p>Este componente devuelve {@code true} mientras estemos dentro de la
 * ventana de gracia. Los checks deben consultarlo:
 * <pre>
 *   if (warmup.inGrace(player)) return;
 * </pre>
 *
 * <p>Solo aplica a checks listados en
 * {@code tuning.warmup.affected_checks} (default: todos los movement
 * checks). Killaura / Reach / BlockGlitch NUNCA están en gracia.
 */
public final class WarmupGracePeriod {

    private final ArgusPlugin plugin;

    public WarmupGracePeriod(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public boolean inGrace(Player p) {
        return inGrace(p, null);
    }

    public boolean inGrace(Player p, String checkName) {
        if (p == null) return false;
        ConfigurationSection sec = plugin.getConfig()
            .getConfigurationSection("tuning.warmup");
        if (sec == null || !sec.getBoolean("enabled", true)) return false;

        long joinGraceMs = sec.getLong("join_grace_ms", 5_000L);
        long tpGraceMs   = sec.getLong("teleport_grace_ms", 2_000L);

        if (checkName != null) {
            var affected = sec.getStringList("affected_checks");
            if (!affected.isEmpty() && !affected.contains(checkName)) return false;
        }

        var bs = plugin.getPacketEventsBootstrap();
        PacketDataStore.State s = bs != null && bs.getDataStore() != null
            ? bs.getDataStore().peek(p.getUniqueId()) : null;
        if (s == null) return false;

        long now = System.currentTimeMillis();
        if (now - s.joinMs < joinGraceMs) {
            logSuppressed(p, checkName, "warmup_join:" + (now - s.joinMs) + "ms");
            return true;
        }
        if (s.teleporting && now < s.teleportUntilMs + tpGraceMs) {
            logSuppressed(p, checkName, "warmup_teleport");
            return true;
        }
        return false;
    }

    private void logSuppressed(Player p, String checkName, String cause) {
        if (checkName == null) return; // inGrace(p) sin checkName: caller no-op, no es una supresión real
        try {
            var fp = plugin.getFalsePositiveLogger();
            if (fp != null) fp.record(p, checkName, cause);
        } catch (Throwable ignored) {}
    }
}
