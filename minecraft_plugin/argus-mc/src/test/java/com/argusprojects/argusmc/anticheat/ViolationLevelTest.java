package com.argusprojects.argusmc.anticheat;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ViolationLevelTest {

    @Test
    void hasFourLevels() {
        assertEquals(4, ViolationLevel.values().length);
    }

    @Test
    void orderIsLowMidHighCritical() {
        ViolationLevel[] vals = ViolationLevel.values();
        assertEquals("LOW", vals[0].name());
        assertEquals("MID", vals[1].name());
        assertEquals("HIGH", vals[2].name());
        assertEquals("CRITICAL", vals[3].name());
    }

    @Test
    void valueOfCaseSensitive() {
        assertEquals(ViolationLevel.HIGH, ViolationLevel.valueOf("HIGH"));
        assertThrows(IllegalArgumentException.class,
            () -> ViolationLevel.valueOf("invalid"));
    }
}
