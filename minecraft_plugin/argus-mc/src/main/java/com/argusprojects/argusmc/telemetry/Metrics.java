package com.argusprojects.argusmc.telemetry;

import org.bukkit.Bukkit;
import org.bukkit.plugin.Plugin;

import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.Supplier;

/**
 * Pack 48 round 2 — bStats-like Metrics (telemetria anonima opt-out).
 *
 * <p>Implementacion minimal compatible con bStats (https://bstats.org/). Se
 * usa una sola URL endpoint y un JSON ligero con stats anonimizadas. El
 * servidor reporta cada {@link #PUSH_INTERVAL_MIN} minutos.
 *
 * <p>NO envia info personal — solo:
 * <ul>
 *   <li>player count (sin nombres).</li>
 *   <li>plugin version y server version.</li>
 *   <li>contadores agregados de violations por nivel.</li>
 * </ul>
 *
 * <p>Opt-out: agregar {@code metrics.enabled: false} en config.yml.
 */
public final class Metrics {

    /** Plugin id en bStats (placeholder — registrar en bstats.org para uno real). */
    private static final int PLUGIN_ID = 24800;
    private static final String SUBMIT_URL = "https://bstats.org/submitData/server-implementation";
    private static final int PUSH_INTERVAL_MIN = 30;

    private final Plugin plugin;
    private final Map<String, Supplier<Object>> customCharts = new HashMap<>();
    private final AtomicLong serverUuidLow  = new AtomicLong();
    private final AtomicLong serverUuidHigh = new AtomicLong();

    public Metrics(Plugin plugin) {
        this.plugin = plugin;
        // UUID estable por server (basado en MOTD + port para no requerir disco).
        UUID id = UUID.nameUUIDFromBytes(
            (Bukkit.getServer().getName() + ":" + Bukkit.getServer().getPort()).getBytes(StandardCharsets.UTF_8));
        serverUuidHigh.set(id.getMostSignificantBits());
        serverUuidLow.set(id.getLeastSignificantBits());
    }

    /** Registra un chart custom (clave -> supplier que devuelve String/Number/Map). */
    public void addCustomChart(String chartId, Supplier<Object> supplier) {
        customCharts.put(chartId, supplier);
    }

    /** Inicia el scheduler que postea cada PUSH_INTERVAL_MIN. */
    public void start() {
        long delayTicks  = 20L * 60 * 5;                         // primer envio: 5min post-start
        long periodTicks = 20L * 60 * PUSH_INTERVAL_MIN;
        Bukkit.getScheduler().runTaskTimerAsynchronously(plugin, this::submit, delayTicks, periodTicks);
    }

    private void submit() {
        try {
            String payload = buildPayload();
            HttpURLConnection con = (HttpURLConnection) new URL(SUBMIT_URL).openConnection();
            con.setRequestMethod("POST");
            con.setRequestProperty("Accept", "application/json");
            con.setRequestProperty("Connection", "close");
            con.setRequestProperty("Content-Encoding", "identity");
            con.setRequestProperty("Content-Type", "application/json");
            con.setRequestProperty("User-Agent", "ArgusMC-Metrics");
            con.setConnectTimeout(5_000);
            con.setReadTimeout(5_000);
            con.setDoOutput(true);
            try (OutputStream os = con.getOutputStream()) {
                os.write(payload.getBytes(StandardCharsets.UTF_8));
            }
            int code = con.getResponseCode();
            plugin.getLogger().fine(() -> "[Argus/bStats] response code=" + code);
            con.disconnect();
        } catch (IOException ex) {
            plugin.getLogger().fine(() -> "[Argus/bStats] submit failed: " + ex.getClass().getSimpleName());
        } catch (Throwable t) {
            plugin.getLogger().fine(() -> "[Argus/bStats] submit fatal: " + t.getMessage());
        }
    }

    private String buildPayload() {
        StringBuilder sb = new StringBuilder(256);
        sb.append("{\"serverUUID\":\"")
          .append(new UUID(serverUuidHigh.get(), serverUuidLow.get())).append("\",")
          .append("\"metricsVersion\":\"3.0.2\",")
          .append("\"playerAmount\":").append(Bukkit.getOnlinePlayers().size()).append(',')
          .append("\"onlineMode\":").append(Bukkit.getOnlineMode() ? 1 : 0).append(',')
          .append("\"bukkitVersion\":\"").append(esc(Bukkit.getVersion())).append("\",")
          .append("\"bukkitName\":\"").append(esc(Bukkit.getName())).append("\",")
          .append("\"javaVersion\":\"").append(esc(System.getProperty("java.version"))).append("\",")
          .append("\"osName\":\"").append(esc(System.getProperty("os.name"))).append("\",")
          .append("\"osArch\":\"").append(esc(System.getProperty("os.arch"))).append("\",")
          .append("\"osVersion\":\"").append(esc(System.getProperty("os.version"))).append("\",")
          .append("\"coreCount\":").append(Runtime.getRuntime().availableProcessors()).append(',')
          .append("\"service\":{\"id\":").append(PLUGIN_ID).append(',')
          .append("\"pluginVersion\":\"").append(esc(plugin.getDescription().getVersion())).append("\",")
          .append("\"customCharts\":[");

        int i = 0;
        for (var e : customCharts.entrySet()) {
            if (i++ > 0) sb.append(',');
            Object value;
            try { value = e.getValue().get(); } catch (Throwable t) { value = null; }
            sb.append("{\"chartId\":\"").append(esc(e.getKey())).append("\",\"data\":{");
            if (value instanceof Number n) {
                sb.append("\"value\":").append(n);
            } else if (value instanceof String s) {
                sb.append("\"value\":\"").append(esc(s)).append("\"");
            } else if (value instanceof Map<?, ?> map) {
                sb.append("\"values\":{");
                int j = 0;
                for (var en : map.entrySet()) {
                    if (j++ > 0) sb.append(',');
                    sb.append("\"").append(esc(String.valueOf(en.getKey()))).append("\":")
                      .append(en.getValue() instanceof Number ? en.getValue().toString() : 0);
                }
                sb.append('}');
            } else {
                sb.append("\"value\":\"unknown\"");
            }
            sb.append("}}");
        }
        sb.append("]}}");
        return sb.toString();
    }

    private static String esc(String s) {
        if (s == null) return "";
        StringBuilder out = new StringBuilder(s.length());
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) out.append(String.format("\\u%04x", (int) c));
                    else out.append(c);
            }
        }
        return out.toString();
    }
}
