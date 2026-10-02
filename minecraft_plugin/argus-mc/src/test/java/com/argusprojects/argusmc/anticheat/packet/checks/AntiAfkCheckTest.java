package com.argusprojects.argusmc.anticheat.packet.checks;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AntiAfkCheckTest {

    @Test
    void jumpsEveryThreeSecondsExactlyAreMetronome() {
        long[] ring = {0, 3000, 6010, 9005, 12000, 15010};
        assertTrue(AntiAfkCheck.isMetronome(ring, 6));
    }

    @Test
    void humanJumpingInPlaceVaries() {
        long[] ring = {0, 2100, 4900, 6800, 10200, 12000};
        assertFalse(AntiAfkCheck.isMetronome(ring, 6));
    }
}
