package com.argusprojects.argusmc.anticheat.packet;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

class RotationSampleTest {

    @Test
    void storesYawPitchAndTs() {
        PacketDataStore.RotationSample r = new PacketDataStore.RotationSample(45.5f, -22.0f, 12345L);
        assertEquals(45.5f, r.yaw, 1e-6);
        assertEquals(-22.0f, r.pitch, 1e-6);
        assertEquals(12345L, r.tsMs);
    }

    @Test
    void chatSampleStoresMessage() {
        PacketDataStore.ChatSample c = new PacketDataStore.ChatSample("hola", 99L);
        assertEquals("hola", c.message);
        assertEquals(99L, c.tsMs);
    }
}
