package com.argusprojects.argusmc.anticheat.packet.checks;

import org.junit.jupiter.api.Test;

import java.util.Random;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class BowAimbotCheckTest {

    /** Objetivo cruzando la pantalla a 1.2 grados/tick durante 20 ticks. */
    private static BowAimbotCheck.Track track(double lead, double noise, long seed) {
        Random r = new Random(seed);
        BowAimbotCheck.Track t = new BowAimbotCheck.Track();
        double jitter = 0;
        for (int i = 0; i < 26; i++) {
            jitter = jitter * 0.6 + r.nextGaussian() * noise;   // la mano corrige a saltos
            t.add(Math.abs(lead + jitter), i * 1.2, 2.0);
        }
        return t;
    }

    @Test
    void aimbotWithConstantLeadIsLockedOn() {
        BowAimbotCheck.Track t = track(2.5, 0.05, 1);
        assertTrue(t.motion() > 1.0);
        assertTrue(BowAimbotCheck.isLockedOn(t, 0.35));
    }

    @Test
    void humanTrackingCorrectsInJumps() {
        for (long seed = 1; seed <= 20; seed++) {
            assertFalse(BowAimbotCheck.isLockedOn(track(2.5, 2.5, seed), 0.35), "seed " + seed);
        }
    }
}
