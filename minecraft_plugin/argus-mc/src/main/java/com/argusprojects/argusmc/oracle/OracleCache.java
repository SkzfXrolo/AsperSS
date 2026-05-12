package com.argusprojects.argusmc.oracle;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Pack 48 round 3 — LRU cache de respuestas del Oracle por
 * (player UUID, check name).
 *
 * <p>El objetivo del cache es evitar llamadas HTTP repetidas para el
 * mismo (player, check) en una ventana corta. Cada entry tiene TTL
 * configurable; al expirar se descarta y se vuelve a consultar el
 * Oracle si hace falta.
 *
 * <p>Thread-safe via {@code synchronized}; capacity-bounded por
 * {@code MAX_ENTRIES} (default 1024) — al exceder, LRU eviction.
 */
public final class OracleCache {

    public static final int MAX_ENTRIES = 1024;

    public static final class Decision {
        public final double weight;
        public final String label;
        public final long   cachedAtMs;
        public final long   ttlMs;
        public Decision(double weight, String label, long ttlMs) {
            this.weight = weight;
            this.label  = label;
            this.cachedAtMs = System.currentTimeMillis();
            this.ttlMs = ttlMs;
        }
        public boolean isExpired() {
            return System.currentTimeMillis() - cachedAtMs > ttlMs;
        }
    }

    private final Map<String, Decision> cache;

    public OracleCache() {
        // accessOrder=true => LRU.
        this.cache = new LinkedHashMap<String, Decision>(64, 0.75f, true) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, Decision> eldest) {
                return size() > MAX_ENTRIES;
            }
        };
    }

    public synchronized Decision get(UUID uuid, String checkName) {
        if (uuid == null || checkName == null) return null;
        Decision d = cache.get(key(uuid, checkName));
        if (d == null) return null;
        if (d.isExpired()) {
            cache.remove(key(uuid, checkName));
            return null;
        }
        return d;
    }

    public synchronized void put(UUID uuid, String checkName, Decision d) {
        if (uuid == null || checkName == null || d == null) return;
        cache.put(key(uuid, checkName), d);
    }

    public synchronized int size() {
        return cache.size();
    }

    public synchronized void clear() {
        cache.clear();
    }

    private static String key(UUID uuid, String checkName) {
        return uuid.toString() + "|" + checkName;
    }
}
