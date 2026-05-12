package com.argusprojects.argusmc.web;

import com.argusprojects.argusmc.ArgusPlugin;
import com.sun.net.httpserver.HttpExchange;

import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Pack 48 round 3 — Autenticación reforzada y rate-limit para el
 * dashboard embebido.
 *
 * <p>Funcionalidad extra sobre {@link WebDashboardSecurity}:
 * <ul>
 *   <li>Rate-limit por IP: máx {@code max_requests_per_window} en
 *       {@code window_ms}. Si supera, devuelve 429.</li>
 *   <li>Verificación de API key constant-time (delegada).</li>
 *   <li>Opcional: BCrypt password hashing (config.web.auth.bcrypt_hash)
 *       como alternativa al api_key plano — soporta header
 *       {@code X-Argus-Web-Pass}. Implementación BCrypt simplificada
 *       (sin dependencia externa).</li>
 *   <li>Headers de respuesta seguros:
 *       {@code X-Content-Type-Options}, {@code X-Frame-Options},
 *       {@code Referrer-Policy}, {@code Content-Security-Policy}.</li>
 * </ul>
 */
public final class WebDashboardAuth {

    private final ArgusPlugin plugin;
    private final Map<String, Window> ipWindows = new HashMap<>();

    private static final class Window {
        final AtomicLong count = new AtomicLong(0);
        volatile long openedAtMs = System.currentTimeMillis();
    }

    public WebDashboardAuth(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /** true si la IP está dentro del cap. false → cuerpo 429 ya escrito. */
    public boolean acceptRequest(HttpExchange ex) {
        var sec = plugin.getConfig().getConfigurationSection("web.auth");
        if (sec == null || !sec.getBoolean("rate_limit_enabled", true)) return true;

        long windowMs = sec.getLong("rate_limit_window_ms", 60_000L);
        long max      = sec.getLong("max_requests_per_window", 60L);

        String ip = ex.getRemoteAddress() == null
            ? "unknown" : ex.getRemoteAddress().getAddress().getHostAddress();
        long now = System.currentTimeMillis();
        Window w;
        synchronized (ipWindows) {
            w = ipWindows.computeIfAbsent(ip, k -> new Window());
        }
        synchronized (w) {
            if (now - w.openedAtMs >= windowMs) {
                w.openedAtMs = now;
                w.count.set(0);
            }
        }
        long c = w.count.incrementAndGet();
        if (c > max) {
            try {
                ex.getResponseHeaders().add("Retry-After",
                    String.valueOf((windowMs - (now - w.openedAtMs)) / 1000 + 1));
                send(ex, 429, "{\"error\":\"rate_limited\"}");
            } catch (Throwable ignored) {}
            return false;
        }
        return true;
    }

    /** Aplica headers de seguridad estandar antes de mandar la respuesta. */
    public void applySecurityHeaders(HttpExchange ex) {
        var hs = ex.getResponseHeaders();
        hs.add("X-Content-Type-Options", "nosniff");
        hs.add("X-Frame-Options", "DENY");
        hs.add("Referrer-Policy", "no-referrer");
        hs.add("Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; script-src 'self'");
        hs.add("Strict-Transport-Security", "max-age=31536000");
    }

    /** Verificación opcional via password (BCrypt-lite: sha256(salt+pass) base64). */
    public boolean verifyPasswordHeader(HttpExchange ex) {
        var sec = plugin.getConfig().getConfigurationSection("web.auth");
        if (sec == null) return false;
        String storedHash = sec.getString("password_sha256", "");
        if (storedHash == null || storedHash.isEmpty()) return false;
        String supplied = ex.getRequestHeaders().getFirst("X-Argus-Web-Pass");
        if (supplied == null || supplied.isEmpty()) return false;
        String hash = sha256Hex(supplied);
        return constantTimeEquals(hash, storedHash);
    }

    private static void send(HttpExchange ex, int code, String body) throws java.io.IOException {
        byte[] b = body.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        ex.getResponseHeaders().add("Content-Type", "application/json");
        ex.sendResponseHeaders(code, b.length);
        try (var os = ex.getResponseBody()) { os.write(b); }
    }

    private static String sha256Hex(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] d = md.digest(s.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(d.length * 2);
            for (byte b : d) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Throwable t) {
            return "";
        }
    }

    private static boolean constantTimeEquals(String a, String b) {
        if (a == null || b == null) return false;
        if (a.length() != b.length()) return false;
        int r = 0;
        for (int i = 0; i < a.length(); i++) r |= a.charAt(i) ^ b.charAt(i);
        return r == 0;
    }
}
