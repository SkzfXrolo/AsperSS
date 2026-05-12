package com.argusprojects.argusmc.web;

import com.argusprojects.argusmc.ArgusPlugin;
import com.sun.net.httpserver.HttpExchange;

import java.util.List;

/**
 * Pack 48 round 3 — CORS configurable para los endpoints REST.
 *
 * <p>Default: deny todo (no CORS) — un dashboard externo debe usar la
 * misma origin o un proxy reverso. Para integración con un panel React
 * externo, agregar el origin a {@code web.cors.allowed_origins}.
 *
 * <h3>Config</h3>
 * <pre>
 * web:
 *   cors:
 *     enabled: false
 *     allowed_origins:
 *       - "https://argus.example.com"
 *       - "http://localhost:5173"
 *     allowed_methods: ["GET", "OPTIONS"]
 *     allow_credentials: false
 *     max_age_s: 600
 * </pre>
 */
public final class WebDashboardCors {

    private final ArgusPlugin plugin;

    public WebDashboardCors(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /** Aplica CORS headers al request si la origin matchea allowlist. */
    public void applyHeaders(HttpExchange ex) {
        var sec = plugin.getConfig().getConfigurationSection("web.cors");
        if (sec == null || !sec.getBoolean("enabled", false)) return;

        String origin = ex.getRequestHeaders().getFirst("Origin");
        if (origin == null) return;

        List<String> allowed = sec.getStringList("allowed_origins");
        if (!allowed.contains(origin) && !allowed.contains("*")) return;

        var hs = ex.getResponseHeaders();
        hs.add("Access-Control-Allow-Origin", origin);
        hs.add("Vary", "Origin");

        List<String> methods = sec.getStringList("allowed_methods");
        if (methods.isEmpty()) methods = List.of("GET", "OPTIONS");
        hs.add("Access-Control-Allow-Methods", String.join(",", methods));

        if (sec.getBoolean("allow_credentials", false)) {
            hs.add("Access-Control-Allow-Credentials", "true");
        }
        hs.add("Access-Control-Max-Age", String.valueOf(sec.getLong("max_age_s", 600L)));
        hs.add("Access-Control-Allow-Headers", "Content-Type, X-Argus-Web-Key, X-Argus-Web-Pass");
    }

    /** true si el request es un preflight OPTIONS (responder 204). */
    public boolean handlePreflight(HttpExchange ex) {
        if (!"OPTIONS".equalsIgnoreCase(ex.getRequestMethod())) return false;
        applyHeaders(ex);
        try {
            ex.sendResponseHeaders(204, -1);
        } catch (Throwable ignored) {}
        return true;
    }
}
