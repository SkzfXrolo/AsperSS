package com.argusprojects.argusmc.tuning;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.entity.Player;

import java.util.ArrayDeque;
import java.util.Deque;

/**
 * Pack 48 round 3 — Log estructurado de violations canceladas.
 *
 * <p>Cuando un check decide "esto parece un cheat pero hay
 * justificación legítima (lag, warmup, slime, etc.)" puede llamar a
 * {@link #record(Player, String, String)} para que quede el evento
 * registrado para tuning posterior.
 *
 * <p>Mantiene un ring buffer de los últimos {@code MAX_CANCELLED}
 * eventos accesible por {@code /argus admin stats} o el web dashboard.
 *
 * <h3>Output format</h3>
 * <pre>
 *   [Argus/FP] uuid=... player=... check=... cause=...
 * </pre>
 * Esto se loguea a level FINE (no INFO) — solo aparece si
 * {@code logging.fp_verbose: true} o con {@code -Djava.util.logging.config}.
 */
public final class FalsePositiveLogger {

    public static final int MAX_CANCELLED = 200;

    private final ArgusPlugin plugin;
    private final Deque<Entry> recent = new ArrayDeque<>();
    private long totalLogged;

    public static final class Entry {
        public final long   tsMs;
        public final String playerName;
        public final java.util.UUID playerUuid;
        public final String checkName;
        public final String cause;
        public Entry(long ts, String name, java.util.UUID uuid, String check, String cause) {
            this.tsMs = ts; this.playerName = name; this.playerUuid = uuid;
            this.checkName = check; this.cause = cause;
        }
    }

    public FalsePositiveLogger(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void record(Player p, String checkName, String cause) {
        if (p == null || checkName == null) return;
        Entry e = new Entry(System.currentTimeMillis(),
            p.getName(), p.getUniqueId(), checkName, cause == null ? "" : cause);
        synchronized (recent) {
            recent.addLast(e);
            while (recent.size() > MAX_CANCELLED) recent.pollFirst();
            totalLogged++;
        }
        if (plugin.getConfig().getBoolean("logging.fp_verbose", false)) {
            plugin.getLogger().fine(() -> "[Argus/FP] uuid=" + e.playerUuid
                + " player=" + e.playerName + " check=" + e.checkName + " cause=" + e.cause);
        }
    }

    /** Snapshot inmutable de los últimos eventos. */
    public java.util.List<Entry> snapshot() {
        synchronized (recent) {
            return new java.util.ArrayList<>(recent);
        }
    }

    public long totalLogged() {
        synchronized (recent) {
            return totalLogged;
        }
    }
}
