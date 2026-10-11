package com.argusprojects.argusmc.anticheat.packet.checks;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertTrue;

class NukerFovCheckTest {

    // Ojo en (0.5, 1.62, 0.5), mirando hacia +Z (yaw 0) y horizontal.
    @Test
    void blockInFrontIsInView() {
        assertTrue(NukerFovCheck.offAngle(0.5, 1.62, 0.5, 0f, 0f, 0, 1, 2) < 20);
    }

    @Test
    void blockBehindIsOutOfView() {
        assertTrue(NukerFovCheck.offAngle(0.5, 1.62, 0.5, 0f, 0f, 0, 1, -3) > 120);
    }

    @Test
    void blockUnderFeetWhileLookingAheadIsOutOfView() {
        assertTrue(NukerFovCheck.offAngle(0.5, 1.62, 0.5, 0f, 0f, 2, -1, 0) > 50);
    }
}
