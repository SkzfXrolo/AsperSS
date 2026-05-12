package com.argusprojects.argusmc.oracle;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Pack 48 round 3 — Heartbeat periódico al backend Argus.
 *
 * <p>Cada {@code heartbeat_interval_s} segundos enviá al
 * {@code heartbeat_url} un JSON con:
 * <pre>
 * {
 *   "server": "minecraft-paper-1",
 *   "version": "1.0.0",
 *   "mc_version": "1.21.3",
 *   "online_players": 12,
 *   "checks_active": 28,
 *   "uptime_ms": 1234567,
 *   "tps": 19.8
 * }
 * </pre>
 *
 * <p>El backend usa esto para mostrar el server en la lista "instalaciones
 * Argus activas" del dashboard global y para enriquecer evaluations
 * Oracle con contexto agregado.
 *
 * <p>Si {@code oracle.heartbeat_url} está vacío, el heartbeat queda
 * dormido — no consume recursos.
 */
public final class OracleHeartbeat {

    private final ArgusPlugin plugin;
    private final OracleConfig cfg;
    private final HttpClient http;
    private final ScheduledExecutorService scheduler;
    private final long startedMs;
    private volatile boolean running;

    public OracleHeartbeat(ArgusPlugin plugin, OracleConfig cfg) {
        this.plugin = plugin;
        this.cfg = cfg;
        this.http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(2))
            .build();
        this.scheduler = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "Argus-OracleHeartbeat");
            t.setDaemon(true);
            return t;
        });
        this.startedMs = System.currentTimeMillis();
    }

    public synchronized void start() {
        if (running) return;
        if (!cfg.enabled || cfg.heartbeatUrl == null || cfg.heartbeatUrl.isEmpty()) {
            plugin.getLogger().fine("[Argus/Oracle] heartbeat dormido (sin URL configurada).");
            return;
        }
        long interval = Math.max(15L, cfg.heartbeatIntervalSec);
        scheduler.scheduleAtFixedRate(this::tick, interval, interval, TimeUnit.SECONDS);
        running = true;
        plugin.getLogger().info("[Argus/Oracle] Heartbeat ON cada " + interval + "s.");
    }

    public synchronized void shutdown() {
        running = false;
        try { scheduler.shutdownNow(); } catch (Throwable ignored) {}
    }

    private void tick() {
        try {
            String payload = buildPayload();
            HttpRequest req = HttpRequest.newBuilder()
                .uri(URI.create(cfg.heartbeatUrl))
                .timeout(Duration.ofSeconds(5))
                .header("Content-Type", "application/json")
                .header("X-Argus-Oracle-Key", cfg.apiKey)
                .header("X-Argus-Source", "argus-mc")
                .POST(HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8))
                .build();
            http.sendAsync(req, HttpResponse.BodyHandlers.discarding())
                .exceptionally(ex -> {
                    plugin.getLogger().fine(() -> "[Argus/Oracle] hb err: "
                        + ex.getClass().getSimpleName() + " " + ex.getMessage());
                    return null;
                });
        } catch (Throwable t) {
            plugin.getLogger().fine(() -> "[Argus/Oracle] hb build err: " + t.getMessage());
        }
    }

    private String buildPayload() {
        long uptime = System.currentTimeMillis() - startedMs;
        int  online = 0;
        try { online = Bukkit.getOnlinePlayers().size(); } catch (Throwable ignored) {}
        double tps = 20.0;
        try {
            double[] arr = Bukkit.getServer().getTPS();
            if (arr != null && arr.length > 0) tps = arr[0];
        } catch (Throwable ignored) {}
        String serverId = plugin.getConfig().getString("argus.server_id", Bukkit.getServer().getName());
        String mcVersion = Bukkit.getServer().getVersion();
        StringBuilder sb = new StringBuilder(192);
        sb.append('{');
        sb.append("\"server\":\"").append(esc(serverId)).append("\",");
        sb.append("\"version\":\"").append(plugin.getPluginMeta().getVersion()).append("\",");
        sb.append("\"mc_version\":\"").append(esc(mcVersion)).append("\",");
        sb.append("\"online_players\":").append(online).append(',');
        sb.append("\"uptime_ms\":").append(uptime).append(',');
        sb.append("\"tps\":").append(String.format(java.util.Locale.ROOT, "%.2f", tps));
        sb.append('}');
        return sb.toString();
    }

    private static String esc(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", " ").replace("\r", " ");
    }
}
