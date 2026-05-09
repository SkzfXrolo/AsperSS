package com.argusprojects.argusmc.api;

import com.argusprojects.argusmc.ArgusConfig;
import com.argusprojects.argusmc.ArgusPlugin;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.logging.Level;

/**
 * Cliente HTTP minimalista que habla con /api/plugin/* del backend Argus.
 *
 * <p>Usa java.net.http.HttpClient (incluido en Java 11+, sobra en Java 17).
 * Parsing JSON casero — solo necesitamos extraer 4 campos string/int. No
 * arrastramos Gson para no inflar el .jar.
 */
public final class ArgusApiClient {

    private final ArgusPlugin plugin;
    private final ArgusConfig cfg;
    private final HttpClient http;
    private final ExecutorService executor;

    public ArgusApiClient(ArgusPlugin plugin, ArgusConfig cfg) {
        this.plugin = plugin;
        this.cfg = cfg;
        this.executor = Executors.newFixedThreadPool(2, r -> {
            Thread t = new Thread(r, "ArgusMC-HTTP");
            t.setDaemon(true);
            return t;
        });
        this.http = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(cfg.getTimeoutSeconds()))
            .executor(this.executor)
            .build();
    }

    public void shutdown() {
        try { executor.shutdown(); } catch (Exception ignored) {}
    }

    /**
     * Pide al backend que emita un token de scan asociado a este server/staff.
     *
     * @param staff  nombre MC del staff que ejecuto /ss
     * @param target nombre MC del jugador objetivo (puede ser null)
     * @param reason razon (puede ser null o vacia)
     */
    public CompletableFuture<TokenResponse> issueTokenAsync(String staff, String target, String reason) {
        return CompletableFuture.supplyAsync(() -> issueTokenSync(staff, target, reason), executor);
    }

    public CompletableFuture<HealthResponse> healthCheckAsync() {
        return CompletableFuture.supplyAsync(this::healthCheckSync, executor);
    }

    private TokenResponse issueTokenSync(String staff, String target, String reason) {
        try {
            String url = cfg.getBaseUrl() + "/api/plugin/issue-token";
            Map<String, String> body = new HashMap<>();
            body.put("staff", staff);
            if (target != null && !target.isEmpty()) body.put("target", target);
            if (reason != null && !reason.isEmpty()) body.put("reason", reason);
            String json = JsonMini.toJson(body);

            HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(cfg.getTimeoutSeconds()))
                .header("Content-Type", "application/json")
                .header("X-Argus-Plugin-Key", cfg.getApiKey())
                .header("User-Agent", "ArgusMC-Plugin/" + plugin.getDescription().getVersion())
                .POST(HttpRequest.BodyPublishers.ofString(json))
                .build();

            HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
            return TokenResponse.parse(resp.statusCode(), resp.body());
        } catch (Exception ex) {
            plugin.getLogger().log(Level.WARNING, "Argus issueToken error: " + ex.getMessage());
            return TokenResponse.error(ex.getClass().getSimpleName() + ": " + ex.getMessage());
        }
    }

    private HealthResponse healthCheckSync() {
        try {
            String url = cfg.getBaseUrl() + "/api/plugin/health";
            HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(url))
                .timeout(Duration.ofSeconds(cfg.getTimeoutSeconds()))
                .header("User-Agent", "ArgusMC-Plugin/" + plugin.getDescription().getVersion())
                .GET();
            if (!cfg.isMisconfigured()) {
                b.header("X-Argus-Plugin-Key", cfg.getApiKey());
            }
            HttpResponse<String> resp = http.send(b.build(), HttpResponse.BodyHandlers.ofString());
            return HealthResponse.parse(resp.statusCode(), resp.body());
        } catch (Exception ex) {
            return HealthResponse.error(ex.getClass().getSimpleName() + ": " + ex.getMessage());
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Anti-Cheat: reportar violations al backend Argus + Discord
    // ──────────────────────────────────────────────────────────────────────

    /**
     * POSTea una violation al backend para que aparezca en el panel
     * staff (pestaña Anti-Cheat). Fire-and-forget: si falla, solo
     * loguea WARNING. El gameplay no se bloquea.
     */
    public void reportViolationAsync(com.argusprojects.argusmc.anticheat.Violation v) {
        executor.submit(() -> {
            try {
                String url = cfg.getBaseUrl() + "/api/plugin/violation";
                java.util.Map<String, String> body = new java.util.HashMap<>();
                body.put("player_uuid", v.playerUuid.toString());
                body.put("player_name", v.playerName);
                body.put("check_name",  v.checkName);
                body.put("level",       v.level.name());
                body.put("details",     v.details);
                body.put("ts_ms",       String.valueOf(v.timestampMs));
                String json = JsonMini.toJson(body);

                HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(cfg.getTimeoutSeconds()))
                    .header("Content-Type", "application/json")
                    .header("X-Argus-Plugin-Key", cfg.getApiKey())
                    .header("User-Agent", "ArgusMC-Plugin/" + plugin.getDescription().getVersion())
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();
                HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
                if (resp.statusCode() >= 400) {
                    plugin.getLogger().log(Level.FINE, "Argus reportViolation HTTP " + resp.statusCode() + ": " + resp.body());
                }
            } catch (Exception ex) {
                plugin.getLogger().log(Level.FINE, "Argus reportViolation error: " + ex.getMessage());
            }
        });
    }

    /**
     * Envia un embed a un webhook de Discord con la violation.
     * El color depende del nivel (LOW=amarillo, MID=naranja, HIGH=rojo, CRITICAL=morado oscuro).
     */
    public void sendDiscordWebhookAsync(String webhookUrl, com.argusprojects.argusmc.anticheat.Violation v) {
        executor.submit(() -> {
            try {
                int color;
                switch (v.level) {
                    case CRITICAL: color = 0x550066; break;
                    case HIGH:     color = 0xCC0000; break;
                    case MID:      color = 0xFF8800; break;
                    default:       color = 0xFFCC00; break;
                }
                // Serializamos el embed a mano (JsonMini no soporta nesting).
                String title   = "Argus AC · " + v.level.name() + " · " + v.checkName;
                String desc    = "**Jugador:** `" + v.playerName + "`\n"
                               + "**Detalle:** " + v.details;
                String json = "{\"username\":\"Argus AntiCheat\","
                            + "\"embeds\":[{\"title\":\"" + JsonMini.escape(title) + "\","
                            + "\"description\":\"" + JsonMini.escape(desc) + "\","
                            + "\"color\":" + color + ","
                            + "\"timestamp\":\"" + java.time.Instant.ofEpochMilli(v.timestampMs).toString() + "\""
                            + "}]}";

                HttpRequest req = HttpRequest.newBuilder(URI.create(webhookUrl))
                    .timeout(Duration.ofSeconds(cfg.getTimeoutSeconds()))
                    .header("Content-Type", "application/json")
                    .header("User-Agent", "ArgusMC-Plugin/" + plugin.getDescription().getVersion())
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();
                HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
                if (resp.statusCode() >= 400) {
                    plugin.getLogger().log(Level.FINE, "Discord webhook HTTP " + resp.statusCode() + ": " + resp.body());
                }
            } catch (Exception ex) {
                plugin.getLogger().log(Level.FINE, "Discord webhook error: " + ex.getMessage());
            }
        });
    }
}
