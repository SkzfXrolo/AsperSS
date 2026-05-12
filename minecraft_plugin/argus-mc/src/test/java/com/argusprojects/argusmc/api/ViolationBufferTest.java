package com.argusprojects.argusmc.api;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.UUID;
import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ViolationBufferTest {

    private ArgusPlugin plugin;
    private ArgusApiClient api;
    private ViolationBuffer buffer;

    @BeforeEach
    void setup() {
        plugin = mock(ArgusPlugin.class);
        when(plugin.getLogger()).thenReturn(Logger.getLogger("test"));
        api = mock(ArgusApiClient.class);
        buffer = new ViolationBuffer(plugin, api);
    }

    @AfterEach
    void teardown() {
        buffer.shutdown();
    }

    private Violation v() {
        Player p = mock(Player.class);
        when(p.getName()).thenReturn("Test");
        when(p.getUniqueId()).thenReturn(UUID.randomUUID());
        return new Violation(p, "reach", ViolationLevel.MID, "x");
    }

    @Test
    void initiallyEmpty() {
        assertEquals(0, buffer.queueSize());
        assertEquals(0, buffer.sentTotal());
        assertEquals(0, buffer.droppedTotal());
    }

    @Test
    void offerIncrementsQueueSize() {
        buffer.offer(v());
        assertEquals(1, buffer.queueSize());
    }

    @Test
    void offerNullIsIgnored() {
        buffer.offer(null);
        assertEquals(0, buffer.queueSize());
    }

    @Test
    void droppedWhenOverCap() {
        // CAP es 1000 — pusheamos 1200 y verificamos drop.
        for (int i = 0; i < 1200; i++) buffer.offer(v());
        assertTrue(buffer.droppedTotal() > 0, "deberian haberse descartado violations");
    }
}
