package com.argusprojects.argusmc.anticheat.packet.checks;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class FastPlaceRhythmTest {

    private static long[] seq(long... dts) {
        long[] t = new long[dts.length + 1];
        for (int i = 0; i < dts.length; i++) t[i + 1] = t[i] + dts[i];
        return t;
    }

    @Test
    void heldFastPlaceEveryTwoTicksIsMachine() {
        assertTrue(FastPlaceCheck.isMachineRhythm(seq(100, 98, 103, 100, 101, 99, 100, 102, 97, 100), 10));
    }

    @Test
    void humanSpamClickMixesTickIntervals() {
        assertFalse(FastPlaceCheck.isMachineRhythm(seq(50, 100, 100, 50, 150, 100, 50, 100, 150, 50), 10));
    }

    @Test
    void vanillaHoldEveryFourTicksIsNotFlagged() {
        assertFalse(FastPlaceCheck.isMachineRhythm(seq(200, 200, 201, 199, 200, 200, 200, 201, 199, 200), 10));
    }
}
