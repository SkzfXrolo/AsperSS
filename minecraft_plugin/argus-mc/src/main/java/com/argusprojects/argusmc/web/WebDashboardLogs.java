package com.argusprojects.argusmc.web;

import com.argusprojects.argusmc.ArgusPlugin;
import com.sun.net.httpserver.HttpExchange;

import java.util.ArrayDeque;
import java.util.Deque;

/**
 * Pack 48 round 3 — Log estructurado de requests al dashboard.
 *
 * <p>Mantiene un ring buffer de las últimas {@code MAX_ENTRIES}
 * requests (default 500) accesible via {@code /api/admin/logs} (admin
 * authenticated only). Útil para auditar accesos al panel.
 *
 * <p>Entries:
 * <pre>
 *   {
 *     "ts": 1730000000000,
 *     "ip": "192.168.1.5",
 *     "method": "GET",
 *     "path": "/api/violations",
 *     "status": 200,
 *     "duration_ms": 12,
 *     "ua": "curl/8.0.1"
 *   }
 * </pre>
 */
public final class WebDashboardLogs {

    public static final int MAX_ENTRIES = 500;

    public static final class Entry {
        public final long   tsMs;
        public final String ip;
        public final String method;
        public final String path;
        public final int    status;
        public final long   durationMs;
        public final String userAgent;
        public Entry(long ts, String ip, String method, String path, int status,
                     long duration, String ua) {
            this.tsMs = ts; this.ip = ip; this.method = method; this.path = path;
            this.status = status; this.durationMs = duration; this.userAgent = ua;
        }
    }

    private final ArgusPlugin plugin;
    private final Deque<Entry> entries = new ArrayDeque<>();
    private long totalLogged;

    public WebDashboardLogs(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void record(HttpExchange ex, int status, long durationMs) {
        if (!plugin.getConfig().getBoolean("web.logs.enabled", true)) return;
        String ip = ex.getRemoteAddress() == null
            ? "unknown" : ex.getRemoteAddress().getAddress().getHostAddress();
        String method = ex.getRequestMethod();
        String path   = ex.getRequestURI() == null ? "" : ex.getRequestURI().getPath();
        String ua     = ex.getRequestHeaders().getFirst("User-Agent");
        if (ua == null) ua = "unknown";
        Entry e = new Entry(System.currentTimeMillis(), ip, method, path,
            status, durationMs, ua);
        synchronized (entries) {
            entries.addLast(e);
            while (entries.size() > MAX_ENTRIES) entries.pollFirst();
            totalLogged++;
        }
    }

    public java.util.List<Entry> snapshot() {
        synchronized (entries) {
            return new java.util.ArrayList<>(entries);
        }
    }

    public long totalLogged() {
        synchronized (entries) {
            return totalLogged;
        }
    }
}
