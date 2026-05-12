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
     * Pack 44: Pide al backend AI Oracle que evalue al jugador con la
     * evidencia disponible. Devuelve la accion sugerida (que puede ser
     * MAS SEVERA que la del ViolationManager local) + reasoning humanizado.
     *
     * Async no-bloqueante. Si la API falla, devuelve null y el plugin sigue
     * con la decision local del ViolationManager.
     */
    public java.util.concurrent.CompletableFuture<com.argusprojects.argusmc.anticheat.AiVerdict> evaluateAiAsync(
            com.argusprojects.argusmc.anticheat.Violation v, String pluginAction) {
        return java.util.concurrent.CompletableFuture.supplyAsync(() -> {
            try {
                String url = cfg.getBaseUrl() + "/api/plugin/ai-evaluate";
                java.util.Map<String, String> body = new java.util.HashMap<>();
                body.put("player_uuid", v.playerUuid.toString());
                body.put("player_name", v.playerName);
                body.put("plugin_action", pluginAction == null ? "none" : pluginAction);
                String violationJson = "{\"check_name\":\"" + JsonMini.escape(v.checkName)
                    + "\",\"level\":\"" + JsonMini.escape(v.level.name())
                    + "\",\"details\":\"" + JsonMini.escape(v.details) + "\"}";
                String json = "{\"player_uuid\":\"" + JsonMini.escape(v.playerUuid.toString())
                    + "\",\"player_name\":\"" + JsonMini.escape(v.playerName)
                    + "\",\"plugin_action\":\"" + JsonMini.escape(pluginAction == null ? "none" : pluginAction)
                    + "\",\"violation\":" + violationJson + "}";

                HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(cfg.getTimeoutSeconds()))
                    .header("Content-Type", "application/json")
                    .header("X-Argus-Plugin-Key", cfg.getApiKey())
                    .header("User-Agent", "ArgusMC-Plugin/" + plugin.getDescription().getVersion())
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();
                HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
                if (resp.statusCode() >= 400) {
                    plugin.getLogger().log(Level.FINE, "AI eval HTTP " + resp.statusCode() + ": " + resp.body());
                    return null;
                }
                String b = resp.body();
                Boolean success = JsonMini.findBool(b, "success");
                if (success == null || !success) return null;
                com.argusprojects.argusmc.anticheat.AiVerdict verdict = new com.argusprojects.argusmc.anticheat.AiVerdict();
                verdict.action       = JsonMini.findString(b, "action");
                verdict.mergedAction = JsonMini.findString(b, "merged_action");
                verdict.reasoning    = JsonMini.findString(b, "reasoning");
                verdict.topFactor    = JsonMini.findString(b, "top_factor");
                verdict.score      = JsonMini.findDouble(b, "score", 0.0);
                verdict.confidence = JsonMini.findDouble(b, "confidence", 0.0);
                return verdict;
            } catch (Exception ex) {
                plugin.getLogger().log(Level.FINE, "AI eval error: " + ex.getMessage());
                return null;
            }
        }, executor);
    }

    /**
     * Pack 46 — Chat conversacional con el Oracle.
     *
     * <p>Envia texto libre del staff a {@code POST /api/plugin/assistant/query}
     * y recibe respuesta humanizada del Oracle basada en datos reales.
     *
     * <p>Timeout: 6s (mas que evaluacion normal porque puede invocar
     * resolver de player_ctx con multiples queries SQL).
     */
    public java.util.concurrent.CompletableFuture<AssistantResponse> askAssistantAsync(String text) {
        return java.util.concurrent.CompletableFuture.supplyAsync(() -> {
            AssistantResponse out = new AssistantResponse();
            try {
                String url = cfg.getBaseUrl() + "/api/plugin/assistant/query";
                String json = "{\"text\":\"" + JsonMini.escape(text == null ? "" : text) + "\"}";
                HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(Math.max(6, cfg.getTimeoutSeconds())))
                    .header("Content-Type", "application/json")
                    .header("X-Argus-Plugin-Key", cfg.getApiKey())
                    .header("User-Agent", "ArgusMC-Plugin/" + plugin.getDescription().getVersion())
                    .POST(HttpRequest.BodyPublishers.ofString(json))
                    .build();
                HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
                String body = resp.body();
                if (resp.statusCode() >= 400) {
                    plugin.getLogger().log(Level.FINE, "Assistant HTTP " + resp.statusCode() + ": " + body);
                    out.success = false;
                    out.error = "HTTP " + resp.statusCode();
                    return out;
                }
                Boolean success = JsonMini.findBool(body, "success");
                out.success = success != null && success;
                out.intent = JsonMini.findString(body, "intent");
                out.answer = JsonMini.findString(body, "answer");
                Boolean miss = JsonMini.findBool(body, "missing_data");
                out.missingData = miss != null && miss;
                return out;
            } catch (Exception ex) {
                plugin.getLogger().log(Level.FINE, "Assistant query error: " + ex.getMessage());
                out.success = false;
                out.error = ex.getMessage();
                return out;
            }
        }, executor);
    }

    /**
     * Pack 46 — Pide al backend sugerencias proactivas para staff conectado.
     *
     * <p>El plugin llama a este endpoint cada N min (configurado en
     * config.yml). Las suggestions son mensajes pre-formateados para
     * whisper al staff. Devuelve null si no hay sugerencias activas
     * (server limpio).
     *
     * <p>Endpoint: {@code GET /api/plugin/assistant/proactive-suggestions}.
     * Cada item del array tiene {player_name, score, message}.
     *
     * <p>El plugin parsea solo el array de messages para reducir parsing.
     */
    public java.util.concurrent.CompletableFuture<java.util.List<String>> getProactiveSuggestionsAsync() {
        return java.util.concurrent.CompletableFuture.supplyAsync(() -> {
            try {
                String url = cfg.getBaseUrl() + "/api/plugin/assistant/proactive-suggestions";
                HttpRequest req = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(cfg.getTimeoutSeconds()))
                    .header("X-Argus-Plugin-Key", cfg.getApiKey())
                    .header("User-Agent", "ArgusMC-Plugin/" + plugin.getDescription().getVersion())
                    .GET()
                    .build();
                HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());
                if (resp.statusCode() >= 400) {
                    return java.util.Collections.<String>emptyList();
                }
                return JsonMini.extractMessagesFromSuggestions(resp.body());
            } catch (Exception ex) {
                plugin.getLogger().log(Level.FINE, "Proactive suggestions error: " + ex.getMessage());
                return java.util.Collections.<String>emptyList();
            }
        }, executor);
    }

    /**
     * Envia un embed a un webhook de Discord con la violation.
     *
     * <p>Pack 48 #531-#534: embed rico con fields separados (jugador, check,
     * nivel, detalles), thumbnail con skin del jugador, footer con server
     * name + version, y color por nivel (LOW=amarillo, MID=naranja, HIGH=rojo,
     * CRITICAL=morado oscuro).
     */
    public void sendDiscordWebhookAsync(String webhookUrl, com.argusprojects.argusmc.anticheat.Violation v) {
        executor.submit(() -> {
            try {
                int color;
                String emoji;
                switch (v.level) {
                    case CRITICAL: color = 0x550066; emoji = "CRITICAL"; break;
                    case HIGH:     color = 0xCC0000; emoji = "HIGH";     break;
                    case MID:      color = 0xFF8800; emoji = "MID";      break;
                    default:       color = 0xFFCC00; emoji = "LOW";      break;
                }
                String title = "Argus AC · " + emoji + " · " + v.checkName;
                String serverName = serverName();
                String thumbUrl = "https://crafatar.com/avatars/" + v.playerUuid
                                + "?size=128&overlay=true";
                String ts = java.time.Instant.ofEpochMilli(v.timestampMs).toString();

                // Construimos el embed con fields (cada uno con name + value + inline).
                StringBuilder fields = new StringBuilder();
                fields.append("\"fields\":[")
                      .append("{\"name\":\"Jugador\",\"value\":\"`").append(JsonMini.escape(v.playerName)).append("`\",\"inline\":true},")
                      .append("{\"name\":\"Check\",\"value\":\"`").append(JsonMini.escape(v.checkName)).append("`\",\"inline\":true},")
                      .append("{\"name\":\"Nivel\",\"value\":\"**").append(emoji).append("**\",\"inline\":true},")
                      .append("{\"name\":\"Detalles\",\"value\":\"").append(JsonMini.escape(truncate(v.details, 800))).append("\",\"inline\":false}")
                      .append("]");

                String json = "{\"username\":\"Argus AntiCheat\","
                            + "\"embeds\":[{"
                            +    "\"title\":\""       + JsonMini.escape(title) + "\","
                            +    "\"color\":"         + color + ","
                            +    "\"timestamp\":\""   + ts + "\","
                            +    "\"thumbnail\":{\"url\":\"" + thumbUrl + "\"},"
                            +    "\"footer\":{\"text\":\""
                            +       JsonMini.escape("Argus MC v" + plugin.getDescription().getVersion()
                                       + " · " + serverName) + "\"},"
                            +    fields
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

    private static String truncate(String s, int max) {
        if (s == null) return "";
        if (s.length() <= max) return s;
        return s.substring(0, max - 3) + "...";
    }

    private String serverName() {
        try {
            String motd = org.bukkit.Bukkit.getMotd();
            if (motd == null || motd.isEmpty()) return "Minecraft Server";
            // Strip color codes basicos.
            String clean = motd.replaceAll("(?i)\u00a7[0-9a-fklmnor]", "").trim();
            if (clean.length() > 60) clean = clean.substring(0, 60);
            return clean;
        } catch (Throwable t) {
            return "Minecraft Server";
        }
    }
}
