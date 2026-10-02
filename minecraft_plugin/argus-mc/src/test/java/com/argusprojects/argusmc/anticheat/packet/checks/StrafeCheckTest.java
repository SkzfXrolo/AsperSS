package com.argusprojects.argusmc.anticheat.packet.checks;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class StrafeCheckTest {

    @Test
    void vanillaAirTurnIsAllowed() {
        // Sprint-jump a 0.3/tick; input lateral maximo (0.026) durante un tick.
        double px = 0.3 * 0.91, pz = 0;
        assertFalse(StrafeCheck.isImpossibleTurn(0.3, 0, px, 0.026));
        assertFalse(StrafeCheck.isImpossibleTurn(0.3, 0, px + 0.026, 0));
        assertFalse(StrafeCheck.isImpossibleTurn(0.3, 0, px - 0.026, pz));
    }

    @Test
    void wallCollisionIsNotStrafe() {
        assertFalse(StrafeCheck.isImpossibleTurn(0.3, 0.1, 0.0, 0.09));
    }

    @Test
    void instantNinetyDegreeTurnKeepingSpeedIsStrafe() {
        assertTrue(StrafeCheck.isImpossibleTurn(0.3, 0, 0, 0.3));
        assertTrue(StrafeCheck.isImpossibleTurn(0.3, 0, 0.2, 0.2));
    }
}
