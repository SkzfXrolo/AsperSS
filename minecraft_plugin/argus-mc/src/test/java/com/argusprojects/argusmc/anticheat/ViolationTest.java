package com.argusprojects.argusmc.anticheat;

import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ViolationTest {

    private Player mockPlayer(String name, UUID uuid) {
        Player p = mock(Player.class);
        when(p.getName()).thenReturn(name);
        when(p.getUniqueId()).thenReturn(uuid);
        return p;
    }

    @Test
    void constructorStoresPlayerFields() {
        UUID uuid = UUID.randomUUID();
        Player p = mockPlayer("Steve", uuid);
        Violation v = new Violation(p, "reach", ViolationLevel.HIGH, "dist=4.5");
        assertEquals(uuid, v.playerUuid);
        assertEquals("Steve", v.playerName);
        assertEquals("reach", v.checkName);
        assertEquals(ViolationLevel.HIGH, v.level);
        assertEquals("dist=4.5", v.details);
        assertTrue(v.timestampMs > 0);
    }

    @Test
    void nullDetailsBecomesEmptyString() {
        Player p = mockPlayer("Steve", UUID.randomUUID());
        Violation v = new Violation(p, "reach", ViolationLevel.LOW, null);
        assertEquals("", v.details);
    }

    @Test
    void withLevelReturnsCopy() {
        Player p = mockPlayer("Alex", UUID.randomUUID());
        Violation a = new Violation(p, "speed", ViolationLevel.MID, "x");
        Violation b = a.withLevel(ViolationLevel.CRITICAL);
        assertNotSame(a, b);
        assertEquals(ViolationLevel.CRITICAL, b.level);
        assertEquals(a.playerUuid, b.playerUuid);
        assertEquals(a.checkName, b.checkName);
        assertEquals(a.details, b.details);
        assertEquals(a.timestampMs, b.timestampMs);
    }

    @Test
    void withLevelSameReturnsSameInstance() {
        Player p = mockPlayer("Alex", UUID.randomUUID());
        Violation a = new Violation(p, "x", ViolationLevel.MID, "y");
        Violation b = a.withLevel(ViolationLevel.MID);
        assertSame(a, b);
    }

    @Test
    void toStringHasReadableFormat() {
        Player p = mockPlayer("Pinkraft", UUID.randomUUID());
        Violation v = new Violation(p, "vclip", ViolationLevel.HIGH, "dy=2.0");
        String s = v.toString();
        assertTrue(s.contains("vclip"));
        assertTrue(s.contains("Pinkraft"));
        assertTrue(s.contains("HIGH"));
    }
}
