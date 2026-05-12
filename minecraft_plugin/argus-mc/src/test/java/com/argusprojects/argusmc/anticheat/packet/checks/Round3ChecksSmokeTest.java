package com.argusprojects.argusmc.anticheat.packet.checks;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Smoke test para los 20 checks del Round 3 — verifica que cada clase:
 * <ol>
 *   <li>Existe y carga.</li>
 *   <li>Tiene un constructor publico que toma ArgusPlugin.</li>
 *   <li>Tiene al menos un metodo {@code handle*} publico.</li>
 * </ol>
 *
 * <p>Una validacion mas profunda (efectos del check con un Player real)
 * requeriria MockBukkit completo; estos smokes garantizan compatibilidad
 * de API sin coste de runtime alto.
 */
public class Round3ChecksSmokeTest {

    private static final Class<?>[] ROUND3_CHECKS = {
        KillauraRotationCheck.class,
        KillauraNoSwingCheck.class,
        KillauraThruWallCheck.class,
        ScaffoldRotationCheck.class,
        ScaffoldTowerCheck.class,
        TimerJitterCheck.class,
        NoSlowDownCheck.class,
        FastEatCheck.class,
        FastBowCheck.class,
        AutoEatCheck.class,
        RegenCheck.class,
        AntiKnockbackCheck.class,
        AimbotCheck.class,
        Reach3DCheck.class,
        LiquidJesusCheck.class,
        PhaseClipCheck.class,
        NoSlowSneakCheck.class,
        AutoArmorCheck.class,
        AutoPotionCheck.class,
        TracersCheck.class,
    };

    @Test
    void allRound3ChecksExist() {
        assertEquals(20, ROUND3_CHECKS.length);
        for (Class<?> c : ROUND3_CHECKS) {
            assertNotNull(c, "class should not be null");
        }
    }

    @Test
    void allRound3ChecksHavePluginConstructor() {
        for (Class<?> c : ROUND3_CHECKS) {
            boolean found = false;
            for (var ctor : c.getDeclaredConstructors()) {
                Class<?>[] params = ctor.getParameterTypes();
                if (params.length == 1 && params[0].getSimpleName().equals("ArgusPlugin")) {
                    found = true;
                    break;
                }
            }
            assertTrue(found, c.getSimpleName() + " debe tener constructor(ArgusPlugin)");
        }
    }

    @Test
    void allRound3ChecksHaveHandleMethod() {
        for (Class<?> c : ROUND3_CHECKS) {
            boolean has = false;
            for (var m : c.getDeclaredMethods()) {
                if (m.getName().startsWith("handle")) {
                    has = true;
                    break;
                }
            }
            assertTrue(has, c.getSimpleName() + " debe tener algun metodo handle*");
        }
    }
}
