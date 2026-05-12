package com.argusprojects.argusmc.web;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.bukkit.Bukkit;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Pack 48 round 2 — servidor HTTP embebido para el dashboard / REST API /
 * metrics Prometheus.
 *
 * <p>Usa {@link com.sun.net.httpserver.HttpServer} del JDK — sin dependencias
 * externas (no Spark, no Netty). Es suficiente para 5-10 req/s desde un
 * scraper local de Prometheus.
 *
 * <h3>Endpoints</h3>
 * <ul>
 *   <li>{@code GET /}                   → dashboard HTML minimal.</li>
 *   <li>{@code GET /api/stats}          → JSON resumen global.</li>
 *   <li>{@code GET /api/violations}     → ultimas N violations (JSON array).</li>
 *   <li>{@code GET /api/players}        → players online + ping + vios.</li>
 *   <li>{@code GET /api/checks/status}  → map check_name -&gt; enabled.</li>
 *   <li>{@code GET /metrics}            → texto Prometheus (text/plain).</li>
 * </ul>
 */
public final class WebDashboardServer {

    private final ArgusPlugin plugin;
    private final HttpServer server;
    private final WebDashboardSecurity security;

    public WebDashboardServer(ArgusPlugin plugin) throws IOException {
        this.plugin = plugin;
        ConfigurationSection sec = plugin.getConfig().getConfigurationSection("web");
        int    port    = sec != null ? sec.getInt("port", 0) : 0;
        String apiKey  = sec != null ? sec.getString("api_key", "") : "";
        List<String> ips = sec != null ? sec.getStringList("ip_allowlist") : List.of();
        boolean publicMetrics = sec != null && sec.getBoolean("public_metrics", false);

        this.security = new WebDashboardSecurity(apiKey, ips, publicMetrics);
        this.server = HttpServer.create(new InetSocketAddress("0.0.0.0", port == 0 ? 8765 : port), 16);
        this.server.setExecutor(Executors.newFixedThreadPool(2, r -> {
            Thread t = new Thread(r, "ArgusMC-Web");
            t.setDaemon(true);
            return t;
        }));

        server.createContext("/", this::handleRoot);
        server.createContext("/api/stats",         this::handleStats);
        server.createContext("/api/violations",    this::handleViolations);
        server.createContext("/api/players",       this::handlePlayers);
        server.createContext("/api/checks/status", this::handleChecksStatus);
        server.createContext("/metrics",           this::handleMetrics);
    }

    public void start() {
        server.start();
        plugin.getLogger().info("[Argus/Web] Dashboard activo en puerto " + server.getAddress().getPort());
    }

    public void shutdown() {
        try {
            server.stop(0);
        } catch (Throwable ignored) {}
    }

    public int getPort() { return server.getAddress().getPort(); }

    // ──────────────────────────────────────────────────────────────────────
    //  Handlers
    // ──────────────────────────────────────────────────────────────────────

    private void handleRoot(HttpExchange ex) throws IOException {
        if (!security.authorize(ex)) { send(ex, 401, "text/plain", "401 unauthorized"); return; }
        String html = "<!doctype html><html><head><meta charset='utf-8'><title>Argus MC Dashboard</title>"
            + "<style>body{font-family:system-ui;margin:24px;background:#0c1116;color:#e5e7eb}"
            + "h1{color:#5cb6ff}a{color:#5cb6ff}code{background:#1a1f27;padding:2px 4px;border-radius:3px}</style>"
            + "</head><body><h1>Argus MC Dashboard</h1>"
            + "<p>Endpoints JSON:</p><ul>"
            + "<li><a href='/api/stats?key=...'>/api/stats</a> — resumen global</li>"
            + "<li><a href='/api/violations?key=...'>/api/violations</a> — últimas violations</li>"
            + "<li><a href='/api/players?key=...'>/api/players</a> — players online</li>"
            + "<li><a href='/api/checks/status?key=...'>/api/checks/status</a> — checks on/off</li>"
            + "<li><a href='/metrics'>/metrics</a> — Prometheus exposition</li></ul>"
            + "<p>Auth: agregá <code>?key=&lt;tu_api_key&gt;</code> o el header "
            + "<code>X-Argus-Web-Key</code> a cada request.</p></body></html>";
        send(ex, 200, "text/html; charset=utf-8", html);
    }

    private void handleStats(HttpExchange ex) throws IOException {
        if (!security.authorize(ex)) { send(ex, 401, "application/json", "{\"error\":\"unauthorized\"}"); return; }
        int onlineCount = Bukkit.getOnlinePlayers().size();
        int totalVios = 0;
        for (Player p : Bukkit.getOnlinePlayers()) {
            totalVios += plugin.getViolationManager().countRecent(p.getUniqueId());
        }
        StringBuilder json = new StringBuilder(256);
        json.append("{\"online\":").append(onlineCount)
            .append(",\"violations_window\":").append(totalVios)
            .append(",\"version\":\"").append(esc(plugin.getDescription().getVersion())).append("\"")
            .append(",\"packetevents\":").append(plugin.getPacketEventsBootstrap() != null
                && plugin.getPacketEventsBootstrap().isInitialized())
            .append(",\"server\":\"").append(esc(Bukkit.getName())).append("\"")
            .append(",\"buffer_queued\":").append(plugin.getViolationBuffer() != null
                ? plugin.getViolationBuffer().queueSize() : 0)
            .append(",\"buffer_sent\":").append(plugin.getViolationBuffer() != null
                ? plugin.getViolationBuffer().sentTotal() : 0)
            .append(",\"buffer_dropped\":").append(plugin.getViolationBuffer() != null
                ? plugin.getViolationBuffer().droppedTotal() : 0)
            .append('}');
        send(ex, 200, "application/json", json.toString());
    }

    private void handleViolations(HttpExchange ex) throws IOException {
        if (!security.authorize(ex)) { send(ex, 401, "application/json", "{\"error\":\"unauthorized\"}"); return; }
        List<Violation> snap = plugin.getViolationManager().snapshotGlobalRecent(100);
        StringBuilder json = new StringBuilder(1024);
        json.append('[');
        for (int i = 0; i < snap.size(); i++) {
            if (i > 0) json.append(',');
            Violation v = snap.get(i);
            json.append("{\"player\":\"").append(esc(v.playerName))
                .append("\",\"uuid\":\"").append(v.playerUuid)
                .append("\",\"check\":\"").append(esc(v.checkName))
                .append("\",\"level\":\"").append(v.level.name())
                .append("\",\"details\":\"").append(esc(v.details))
                .append("\",\"ts_ms\":").append(v.timestampMs).append('}');
        }
        json.append(']');
        send(ex, 200, "application/json", json.toString());
    }

    private void handlePlayers(HttpExchange ex) throws IOException {
        if (!security.authorize(ex)) { send(ex, 401, "application/json", "{\"error\":\"unauthorized\"}"); return; }
        StringBuilder json = new StringBuilder(512);
        json.append('[');
        int i = 0;
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (i++ > 0) json.append(',');
            int vios = plugin.getViolationManager().countRecent(p.getUniqueId());
            json.append("{\"name\":\"").append(esc(p.getName()))
                .append("\",\"uuid\":\"").append(p.getUniqueId())
                .append("\",\"ping\":").append(p.getPing())
                .append(",\"violations\":").append(vios)
                .append(",\"gm\":\"").append(p.getGameMode().name())
                .append("\"}");
        }
        json.append(']');
        send(ex, 200, "application/json", json.toString());
    }

    private void handleChecksStatus(HttpExchange ex) throws IOException {
        if (!security.authorize(ex)) { send(ex, 401, "application/json", "{\"error\":\"unauthorized\"}"); return; }
        StringBuilder json = new StringBuilder(1024);
        json.append('{');
        String[] checks = {
            "timer","phase","velocity","invalid_rotation","reach_packet","killaura_swing_packet",
            "aim_snap_packet","ping_spoof","cps_packet","inv_move_packet",
            "vclip","step","speed_packet","fast_place","fast_break","nuker","auto_totem",
            "killaura_aim","killaura_blocking","boat_fly","jetpack","spider",
            "multi_velocity","block_reach","crit","projectile_aim","bow_aim","boat_fly_advanced",
            "hitbox_expansion","backstab","melee_fly",
            "block_glitch","item_pickup","inventory_teleport","liquid_walk",
            "chat_macro","named_item_spam","autoclicker_advanced"
        };
        boolean first = true;
        for (String c : checks) {
            if (!first) json.append(',');
            first = false;
            json.append('"').append(c).append("\":")
                .append(plugin.getAnticheatConfig() != null && plugin.getAnticheatConfig().isCheckEnabled(c));
        }
        json.append('}');
        send(ex, 200, "application/json", json.toString());
    }

    private void handleMetrics(HttpExchange ex) throws IOException {
        if (!security.authorize(ex)) { send(ex, 401, "text/plain", "unauthorized\n"); return; }
        StringBuilder out = new StringBuilder(2048);
        out.append("# HELP argus_online_players Players online\n");
        out.append("# TYPE argus_online_players gauge\n");
        out.append("argus_online_players ").append(Bukkit.getOnlinePlayers().size()).append('\n');

        out.append("# HELP argus_violations_window Total violations in current window\n");
        out.append("# TYPE argus_violations_window gauge\n");
        int totalVios = 0;
        for (Player p : Bukkit.getOnlinePlayers()) {
            totalVios += plugin.getViolationManager().countRecent(p.getUniqueId());
        }
        out.append("argus_violations_window ").append(totalVios).append('\n');

        out.append("# HELP argus_violations_total Total violations seen since plugin start (counter)\n");
        out.append("# TYPE argus_violations_total counter\n");
        Map<String, AtomicLong> byCheck = plugin.getViolationManager().totalByCheck();
        Map<String, AtomicLong> byLevel = plugin.getViolationManager().totalByLevel();
        for (var e : byCheck.entrySet()) {
            out.append("argus_violations_total{check=\"").append(escMetric(e.getKey()))
               .append("\"} ").append(e.getValue().get()).append('\n');
        }
        for (var e : byLevel.entrySet()) {
            out.append("argus_violations_total_by_level{level=\"").append(escMetric(e.getKey()))
               .append("\"} ").append(e.getValue().get()).append('\n');
        }

        if (plugin.getViolationBuffer() != null) {
            out.append("# HELP argus_buffer_queued Violations en cola en el buffer asincrono\n");
            out.append("# TYPE argus_buffer_queued gauge\n");
            out.append("argus_buffer_queued ").append(plugin.getViolationBuffer().queueSize()).append('\n');
            out.append("# HELP argus_buffer_sent_total Violations enviadas al backend (counter)\n");
            out.append("# TYPE argus_buffer_sent_total counter\n");
            out.append("argus_buffer_sent_total ").append(plugin.getViolationBuffer().sentTotal()).append('\n');
            out.append("# HELP argus_buffer_dropped_total Violations descartadas por buffer lleno (counter)\n");
            out.append("# TYPE argus_buffer_dropped_total counter\n");
            out.append("argus_buffer_dropped_total ").append(plugin.getViolationBuffer().droppedTotal()).append('\n');
        }

        send(ex, 200, "text/plain; version=0.0.4", out.toString());
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Util
    // ──────────────────────────────────────────────────────────────────────

    private void send(HttpExchange ex, int status, String contentType, String body) throws IOException {
        byte[] data = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().add("Content-Type", contentType);
        ex.getResponseHeaders().add("X-Argus-Plugin", "1.0");
        ex.sendResponseHeaders(status, data.length);
        try (OutputStream os = ex.getResponseBody()) {
            os.write(data);
        }
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

    private static String escMetric(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ");
    }
}
