package com.argusprojects.argusmc.anticheat.packet.checks;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class AutoClickTickCheckTest {

    private static long[] ticks(int... intervals) {
        long[] t = new long[intervals.length + 1];
        for (int i = 0; i < intervals.length; i++) t[i + 1] = t[i] + intervals[i];
        return t;
    }

    @Test
    void randomizedMacroOnlyHitsOneAndTwoTicks() {
        assertTrue(AutoClickTickCheck.isNarrowTickRhythm(ticks(1, 2, 2, 1, 2, 1, 1, 2, 2, 2, 1, 2)));
    }

    @Test
    void humanHasDoublesOrPauses() {
        assertFalse(AutoClickTickCheck.isNarrowTickRhythm(ticks(1, 2, 0, 2, 1, 3, 2, 1, 2, 1)));
        assertFalse(AutoClickTickCheck.isNarrowTickRhythm(ticks(1, 2, 2, 1, 4, 1, 2, 2, 1, 2)));
    }
}
