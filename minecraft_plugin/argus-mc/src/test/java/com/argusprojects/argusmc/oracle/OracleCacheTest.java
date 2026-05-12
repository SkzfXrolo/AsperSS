package com.argusprojects.argusmc.oracle;

import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

public class OracleCacheTest {

    @Test
    void putAndGetReturnsDecision() {
        OracleCache c = new OracleCache();
        UUID u = UUID.randomUUID();
        c.put(u, "killaura", new OracleCache.Decision(1.2, "likely_cheat", 30_000));
        OracleCache.Decision d = c.get(u, "killaura");
        assertNotNull(d);
        assertEquals(1.2, d.weight, 1e-9);
        assertEquals("likely_cheat", d.label);
    }

    @Test
    void getReturnsNullForUnknown() {
        OracleCache c = new OracleCache();
        assertNull(c.get(UUID.randomUUID(), "killaura"));
    }

    @Test
    void expiredEntryReturnsNullAndRemoves() throws Exception {
        OracleCache c = new OracleCache();
        UUID u = UUID.randomUUID();
        c.put(u, "fly", new OracleCache.Decision(0.5, "lag", 1));
        Thread.sleep(15);
        assertNull(c.get(u, "fly"));
        assertEquals(0, c.size());
    }

    @Test
    void nullArgsHandledSafely() {
        OracleCache c = new OracleCache();
        c.put(null, "x", new OracleCache.Decision(1, "n", 1));
        c.put(UUID.randomUUID(), null, new OracleCache.Decision(1, "n", 1));
        c.put(UUID.randomUUID(), "x", null);
        assertEquals(0, c.size());
        assertNull(c.get(null, "x"));
        assertNull(c.get(UUID.randomUUID(), null));
    }

    @Test
    void differentChecksDoNotCollide() {
        OracleCache c = new OracleCache();
        UUID u = UUID.randomUUID();
        c.put(u, "speed", new OracleCache.Decision(0.7, "a", 10_000));
        c.put(u, "reach", new OracleCache.Decision(1.3, "b", 10_000));
        assertEquals("a", c.get(u, "speed").label);
        assertEquals("b", c.get(u, "reach").label);
    }

    @Test
    void clearResetsCache() {
        OracleCache c = new OracleCache();
        c.put(UUID.randomUUID(), "x", new OracleCache.Decision(1, "n", 10_000));
        c.put(UUID.randomUUID(), "y", new OracleCache.Decision(1, "n", 10_000));
        assertEquals(2, c.size());
        c.clear();
        assertEquals(0, c.size());
    }

    @Test
    void lruEvictsOldestBeyondMax() {
        // Put MAX_ENTRIES + 5, oldest 5 should be evicted.
        OracleCache c = new OracleCache();
        UUID[] uuids = new UUID[OracleCache.MAX_ENTRIES + 5];
        for (int i = 0; i < uuids.length; i++) {
            uuids[i] = UUID.randomUUID();
            c.put(uuids[i], "k", new OracleCache.Decision(1, "n", 60_000));
        }
        assertEquals(OracleCache.MAX_ENTRIES, c.size());
        // El primero (más viejo) ya no debería estar.
        assertNull(c.get(uuids[0], "k"));
        // Uno reciente sí.
        assertNotNull(c.get(uuids[uuids.length - 1], "k"));
    }
}
