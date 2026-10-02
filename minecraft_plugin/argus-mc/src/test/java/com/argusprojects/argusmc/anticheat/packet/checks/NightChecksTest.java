package com.argusprojects.argusmc.anticheat.packet.checks;

import org.junit.jupiter.api.Test;

import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class NightChecksTest {

    private static long[] seq(long... dts) {
        long[] t = new long[dts.length + 1];
        for (int i = 0; i < dts.length; i++) t[i + 1] = t[i] + dts[i];
        return t;
    }

    @Test
    void chestStealerFixedDelayIsMacro() {
        assertTrue(InventoryMacroCheck.isRoboticRhythm(seq(50, 51, 49, 50, 52, 50, 48, 50), 8));
    }

    @Test
    void fast18ShiftClicksTwoTicksApartAreNotMacro() {
        assertFalse(InventoryMacroCheck.isRoboticRhythm(seq(100, 101, 99, 100, 102, 100, 98, 100), 8));
    }

    @Test
    void humanShiftClickingIsNotMacro() {
        assertFalse(InventoryMacroCheck.isRoboticRhythm(seq(140, 210, 160, 300, 180, 150, 240, 190), 8));
    }

    @Test
    void zeroDelayStealerIsMacro() {
        assertTrue(InventoryMacroCheck.isRoboticRhythm(seq(2, 1, 3, 1, 2, 0, 1, 2), 8));
    }

    @Test
    void omniSprintAngle() {
        // yaw 0 mira a +Z: avanzar en +Z es 0 grados, retroceder 180, de costado 90.
        assertEquals(0, OmniSprintCheck.angleToFacing(0f, 0, 0.28), 0.01);
        assertEquals(180, OmniSprintCheck.angleToFacing(0f, 0, -0.28), 0.01);
        assertEquals(90, OmniSprintCheck.angleToFacing(0f, 0.28, 0), 0.01);
    }

    @Test
    void triggerNeedsInstantReactionAndNoAirSwings() {
        assertTrue(TriggerBotCheck.isTrigger(0, 0.0, 10, 0.10));
        assertFalse(TriggerBotCheck.isTrigger(0, 0.45, 10, 0.10));   // spam con swings al aire: humano
        assertFalse(TriggerBotCheck.isTrigger(4, 0.0, 10, 0.10));    // pega con calma: humano
    }

    @Test
    void mouseRotationsKeepTheirGcd() {
        double f = 0.5 * 0.6 + 0.2;
        double step = f * f * f * 1.2;   // sensibilidad 50%
        Random r = new Random(7);
        for (int i = 0; i < 200; i++) {
            float base = (float) (r.nextInt(400) * step - 30);
            float a = (float) (base + (1 + r.nextInt(40)) * step);
            float b = (float) (a + (1 + r.nextInt(40)) * step);
            double d1 = Math.abs(a - base), d2 = Math.abs(b - a);
            assertTrue(AimGcdCheck.gcd(Math.max(d1, d2), Math.min(d1, d2)) >= AimGcdCheck.MIN_MOUSE_STEP * 0.9);
        }
    }

    @Test
    void aimAssistRotationsBreakTheGcd() {
        Random r = new Random(11);
        int broken = 0;
        for (int i = 0; i < 200; i++) {
            double d1 = 0.3 + r.nextDouble() * 3, d2 = 0.3 + r.nextDouble() * 3;
            if (AimGcdCheck.gcd(Math.max(d1, d2), Math.min(d1, d2)) < AimGcdCheck.MIN_MOUSE_STEP * 0.9) broken++;
        }
        assertTrue(broken > 120, "solo " + broken + "/200");
    }

    @Test
    void learnedSensitivityCatchesEqualStepAim() {
        double step = Math.pow(0.5 * 0.6 + 0.2, 3) * 1.2;
        double[] learned = {step, step, 2 * step, step, step, 3 * step, step};
        double est = AimGcdCheck.estimate(learned);
        assertEquals(step, est, 1e-9);
        assertFalse(AimGcdCheck.offGrid(7 * step, est));       // giro de mouse
        assertTrue(AimGcdCheck.offGrid(7.5 * step, est));      // giro calculado (aim assist)
        assertFalse(AimGcdCheck.offGrid(1.0, 0));              // sin sensibilidad aprendida no opina
    }
}
