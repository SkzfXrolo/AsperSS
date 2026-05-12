package com.argusprojects.argusmc.oracle;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

public class OracleDecisionApplierTest {

    private ArgusPlugin plugin;
    private OracleDecisionApplier applier;
    private Player playerMock;

    @BeforeEach
    void setup() {
        plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        ConfigurationSection sec = mock(ConfigurationSection.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getConfigurationSection("oracle.applier")).thenReturn(sec);
        when(sec.getDouble("upgrade_above", 1.2)).thenReturn(1.2);
        when(sec.getDouble("downgrade_below", 0.7)).thenReturn(0.7);
        when(sec.getDouble("suppress_below", 0.4)).thenReturn(0.4);

        playerMock = mock(Player.class);
        when(playerMock.getUniqueId()).thenReturn(UUID.randomUUID());
        when(playerMock.getName()).thenReturn("Tester");

        applier = new OracleDecisionApplier(plugin);
    }

    @Test
    void neutralWeightLeavesViolationUnchanged() {
        Violation v = new Violation(playerMock, "killaura", ViolationLevel.MID, "test");
        Violation r = applier.apply(v, new OracleCache.Decision(1.0, "n", 1));
        assertSame(v, r);
    }

    @Test
    void highWeightEscalatesLevel() {
        Violation v = new Violation(playerMock, "speed", ViolationLevel.MID, "test");
        Violation r = applier.apply(v, new OracleCache.Decision(1.3, "cheat", 1));
        assertEquals(ViolationLevel.HIGH, r.level);
    }

    @Test
    void lowWeightDeescalatesLevel() {
        Violation v = new Violation(playerMock, "speed", ViolationLevel.HIGH, "test");
        Violation r = applier.apply(v, new OracleCache.Decision(0.6, "legit", 1));
        assertEquals(ViolationLevel.MID, r.level);
    }

    @Test
    void veryLowWeightSuppresses() {
        Violation v = new Violation(playerMock, "speed", ViolationLevel.MID, "test");
        Violation r = applier.apply(v, new OracleCache.Decision(0.3, "lag", 1));
        assertNull(r);
    }

    @Test
    void nullViolationReturnsNull() {
        assertNull(applier.apply(null, new OracleCache.Decision(1.0, "x", 1)));
    }

    @Test
    void nullDecisionReturnsViolationUnchanged() {
        Violation v = new Violation(playerMock, "killaura", ViolationLevel.MID, "test");
        assertSame(v, applier.apply(v, null));
    }

    @Test
    void criticalCannotBeEscalated() {
        Violation v = new Violation(playerMock, "speed", ViolationLevel.CRITICAL, "test");
        Violation r = applier.apply(v, new OracleCache.Decision(1.4, "cheat", 1));
        assertEquals(ViolationLevel.CRITICAL, r.level);
    }
}
