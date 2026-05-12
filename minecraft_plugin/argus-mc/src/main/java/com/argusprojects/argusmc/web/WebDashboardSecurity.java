package com.argusprojects.argusmc.web;

import com.sun.net.httpserver.HttpExchange;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * Pack 48 round 2 — autenticacion + ACL para el {@link WebDashboardServer}.
 *
 * <p>Estrategia:
 * <ul>
 *   <li>API key (header {@code X-Argus-Web-Key} o query param {@code key}):
 *       comparada con el valor de config en tiempo constante.</li>
 *   <li>IP whitelist opcional (por defecto solo {@code 127.0.0.1}).</li>
 *   <li>Endpoint {@code /metrics} es publico SOLO si {@code public_metrics}
 *       esta en true (default false) — util para Prometheus scraping local.</li>
 * </ul>
 */
public final class WebDashboardSecurity {

    private final String apiKeyHash;
    private final Set<String> ipAllowlist;
    private final boolean publicMetrics;

    public WebDashboardSecurity(String apiKey, List<String> ipAllowlist, boolean publicMetrics) {
        this.apiKeyHash = sha256(apiKey == null ? "" : apiKey);
        this.ipAllowlist = new HashSet<>();
        if (ipAllowlist != null) this.ipAllowlist.addAll(ipAllowlist);
        if (this.ipAllowlist.isEmpty()) {
            this.ipAllowlist.add("127.0.0.1");
            this.ipAllowlist.add("::1");
            this.ipAllowlist.add("0:0:0:0:0:0:0:1");
        }
        this.publicMetrics = publicMetrics;
    }

    /** Verifica si la request es valida. true → continuar, false → 401. */
    public boolean authorize(HttpExchange ex) {
        InetSocketAddress addr = ex.getRemoteAddress();
        String ip = addr.getAddress().getHostAddress();
        boolean ipOk = ipAllowlist.contains("*") || ipAllowlist.contains(ip);
        if (!ipOk) return false;

        // /metrics publico si esta habilitado.
        if (publicMetrics && ex.getRequestURI().getPath().equals("/metrics")) return true;

        // API key: header tiene prioridad.
        String key = ex.getRequestHeaders().getFirst("X-Argus-Web-Key");
        if (key == null || key.isEmpty()) {
            String q = ex.getRequestURI().getRawQuery();
            if (q != null) {
                for (String part : q.split("&")) {
                    int eq = part.indexOf('=');
                    if (eq > 0 && part.substring(0, eq).equals("key")) {
                        key = part.substring(eq + 1);
                        break;
                    }
                }
            }
        }
        if (key == null) return false;
        return constantTimeEquals(sha256(key), apiKeyHash);
    }

    private static String sha256(String s) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] dig = md.digest(s.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(dig.length * 2);
            for (byte b : dig) sb.append(String.format("%02x", b));
            return sb.toString();
        } catch (Exception ex) {
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
