package com.argusprojects.argusmc.oracle;

import com.argusprojects.argusmc.ArgusPlugin;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

/**
 * Pack 48 round 3 — Cliente HTTP async para el endpoint Oracle ML
 * del backend Argus.
 *
 * <p>El endpoint recibe un JSON describiendo el evento (check name,
 * player UUID, server context, telemetría) y responde con
 * <pre>
 * { "weight": 0.8, "label": "likely_legit" }
 * </pre>
 * El {@code weight} multiplica la severidad del violation antes del
 * threshold (weight 1.0 = no cambio, &gt;1.0 = inflar, &lt;1.0 = atenuar).
 *
 * <p>Diseño:
 * <ul>
 *   <li>Cliente compartido {@link HttpClient} con un thread pool dedicado.</li>
 *   <li>Cada {@link #evaluate} devuelve un {@link CompletableFuture} —
 *       las llamadas son fire-and-forget; el resultado se cachea por
 *       {@link OracleCache} y el siguiente violation del mismo check
 *       lo consulta sin bloquear.</li>
 *   <li>Timeouts cortos (default 1.5s) — un Oracle lento no degrada
 *       el anti-cheat.</li>
 *   <li>Errores se loguean a FINE y devuelven un weight neutro 1.0
 *       (fail-open desde el punto de vista del check).</li>
 * </ul>
 */
public final class OracleClient {

    private final ArgusPlugin plugin;
    private final OracleConfig cfg;
    private final OracleCache cache;
    private final HttpClient http;

    public OracleClient(ArgusPlugin plugin, OracleConfig cfg, OracleCache cache) {
        this.plugin = plugin;
        this.cfg = cfg;
        this.cache = cache;
        this.http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofMillis(Math.max(500L, cfg.timeoutMs / 2)))
            .build();
    }

    /**
     * Evalua un violation. Si el cache tiene una entry fresca, la
     * devuelve sin hacer la llamada. Si no, hace la llamada async y
     * guarda el resultado en el cache.
     */
    public CompletableFuture<OracleCache.Decision> evaluate(
        UUID playerUuid, String playerName, String checkName,
        String level, String details, double trustScore) {

        if (!cfg.hasValidUrl()) {
            return CompletableFuture.completedFuture(neutralDecision());
        }
        OracleCache.Decision cached = cache.get(playerUuid, checkName);
        if (cached != null) {
            return CompletableFuture.completedFuture(cached);
        }

        String payload = buildJson(playerUuid, playerName, checkName, level, details, trustScore);
        HttpRequest req;
        try {
            req = HttpRequest.newBuilder()
                .uri(URI.create(cfg.url))
                .timeout(Duration.ofMillis(cfg.timeoutMs))
                .header("Content-Type", "application/json")
                .header("X-Argus-Oracle-Key", cfg.apiKey)
                .header("X-Argus-Source", "argus-mc")
                .POST(HttpRequest.BodyPublishers.ofString(payload, StandardCharsets.UTF_8))
                .build();
        } catch (Throwable t) {
            plugin.getLogger().fine(() -> "[Argus/Oracle] build err: " + t.getMessage());
            return CompletableFuture.completedFuture(neutralDecision());
        }

        return http.sendAsync(req, HttpResponse.BodyHandlers.ofString())
            .orTimeout(cfg.timeoutMs, TimeUnit.MILLISECONDS)
            .thenApply(resp -> {
                if (resp.statusCode() / 100 != 2) {
                    plugin.getLogger().fine(() -> "[Argus/Oracle] http "
                        + resp.statusCode() + " body=" + resp.body());
                    return neutralDecision();
                }
                OracleCache.Decision d = parseDecision(resp.body());
                cache.put(playerUuid, checkName, d);
                return d;
            })
            .exceptionally(ex -> {
                plugin.getLogger().fine(() -> "[Argus/Oracle] err " + ex.getMessage());
                return neutralDecision();
            });
    }

    private OracleCache.Decision neutralDecision() {
        return new OracleCache.Decision(1.0, "neutral", cfg.cacheTtlMs / 10);
    }

    private OracleCache.Decision parseDecision(String body) {
        if (body == null) return neutralDecision();
        double w = findDouble(body, "weight", 1.0);
        // Clamp segun config.
        if (w < cfg.weightFloor)   w = cfg.weightFloor;
        if (w > cfg.weightCeiling) w = cfg.weightCeiling;
        String label = findString(body, "label", "neutral");
        return new OracleCache.Decision(w, label, cfg.cacheTtlMs);
    }

    private static String findString(String json, String key, String def) {
        String needle = "\"" + key + "\"";
        int i = json.indexOf(needle);
        if (i < 0) return def;
        int q = json.indexOf('"', i + needle.length() + 1);
        if (q < 0) return def;
        int q2 = json.indexOf('"', q + 1);
        if (q2 < 0) return def;
        return json.substring(q + 1, q2);
    }

    private static double findDouble(String json, String key, double def) {
        String needle = "\"" + key + "\"";
        int i = json.indexOf(needle);
        if (i < 0) return def;
        int c = json.indexOf(':', i + needle.length());
        if (c < 0) return def;
        int end = c + 1;
        while (end < json.length() && ",}\n\r".indexOf(json.charAt(end)) < 0) end++;
        try {
            return Double.parseDouble(json.substring(c + 1, end).trim());
        } catch (NumberFormatException ignored) {
            return def;
        }
    }

    private static String buildJson(UUID uuid, String name, String check,
                                    String level, String details, double trust) {
        StringBuilder sb = new StringBuilder(256);
        sb.append('{');
        sb.append("\"player_uuid\":\"").append(uuid).append("\",");
        sb.append("\"player_name\":\"").append(esc(name)).append("\",");
        sb.append("\"check\":\"").append(esc(check)).append("\",");
        sb.append("\"level\":\"").append(esc(level)).append("\",");
        sb.append("\"details\":\"").append(esc(details)).append("\",");
        sb.append("\"trust_score\":").append(trust);
        sb.append('}');
        return sb.toString();
    }

    private static String esc(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\n", "\\n").replace("\r", "\\r");
    }
}
