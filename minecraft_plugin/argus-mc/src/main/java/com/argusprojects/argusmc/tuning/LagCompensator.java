package com.argusprojects.argusmc.tuning;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Bukkit;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — supresor de violations bajo lag.
 *
 * <p>Cuando el TPS del servidor cae por debajo de {@code min_tps} o el ping
 * del jugador supera {@code max_ping_ms}, los checks de movimiento /
 * combate suelen disparar falsos positivos en lote. Este componente
 * decide "ignorar este violation por lag" y lo registra como cancelled.
 *
 * <p>Es un GATE para los checks — se consulta antes de flagear:
 * <pre>
 *   if (lagComp.shouldSuppress(player, "speed_packet")) return;
 * </pre>
 *
 * <p>NOTA: este gate solo es aplicable a checks marcados como
 * "lag-sensitive" en {@code config.yml::tuning.lag_compensation.checks}.
 * Checks como BlockReach o Killaura no son lag-sensitive y NUNCA se
 * suprimen.
 */
public final class LagCompensator {

    private final ArgusPlugin plugin;
    private volatile double cachedTps = 20.0;
    private volatile long   tpsCacheAtMs = 0L;
    private static final long TPS_CACHE_TTL_MS = 1_000L;

    public LagCompensator(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public boolean shouldSuppress(Player player, String checkName) {
        if (player == null) return false;
        ConfigurationSection sec = plugin.getConfig()
            .getConfigurationSection("tuning.lag_compensation");
        if (sec == null || !sec.getBoolean("enabled", true)) return false;

        var checks = sec.getStringList("checks");
        if (!checks.isEmpty() && !checks.contains(checkName)) return false;

        double minTps  = sec.getDouble("min_tps", 18.5);
        long   maxPing = sec.getLong  ("max_ping_ms", 250L);

        long ping = pingMs(player);
        if (ping > maxPing) {
            countCancelled(player.getUniqueId());
            return true;
        }

        double tps = currentTps();
        if (tps < minTps) {
            countCancelled(player.getUniqueId());
            return true;
        }
        return false;
    }

    public double currentTps() {
        long now = System.currentTimeMillis();
        if (now - tpsCacheAtMs < TPS_CACHE_TTL_MS) return cachedTps;
        try {
            // Paper API: Bukkit.getServer().getTPS()[0] = last 1 min.
            double[] tps = Bukkit.getServer().getTPS();
            cachedTps = tps != null && tps.length > 0 ? tps[0] : 20.0;
        } catch (Throwable ignored) {
            cachedTps = 20.0; // si el server no es Paper, asumimos 20.
        }
        tpsCacheAtMs = now;
        return cachedTps;
    }

    public long pingMs(Player p) {
        try {
            return p.getPing();
        } catch (Throwable ignored) {
            return 50L; // Spigot legacy fallback.
        }
    }

    private void countCancelled(java.util.UUID uuid) {
        try {
            var bs = plugin.getPacketEventsBootstrap();
            if (bs == null) return;
            PacketDataStore store = bs.getDataStore();
            if (store == null) return;
            var s = store.peek(uuid);
            if (s != null) s.cancelledViolations++;
        } catch (Throwable ignored) {}
    }
}
