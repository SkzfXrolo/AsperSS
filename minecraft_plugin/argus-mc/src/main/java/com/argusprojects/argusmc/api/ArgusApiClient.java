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
}
