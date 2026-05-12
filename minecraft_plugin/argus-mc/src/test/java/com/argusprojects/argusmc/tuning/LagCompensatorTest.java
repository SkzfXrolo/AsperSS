package com.argusprojects.argusmc.tuning;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

public class LagCompensatorTest {

    @Test
    void disabledReturnsNeverSuppress() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        ConfigurationSection sec = mock(ConfigurationSection.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getConfigurationSection("tuning.lag_compensation")).thenReturn(sec);
        when(sec.getBoolean("enabled", true)).thenReturn(false);

        LagCompensator lc = new LagCompensator(plugin);
        assertFalse(lc.shouldSuppress(mockPlayer(50), "speed_packet"));
    }

    @Test
    void nullPlayerReturnsFalse() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        LagCompensator lc = new LagCompensator(plugin);
        assertFalse(lc.shouldSuppress(null, "speed_packet"));
    }

    @Test
    void checkNotInAllowlistReturnsFalse() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        ConfigurationSection sec = mock(ConfigurationSection.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getConfigurationSection("tuning.lag_compensation")).thenReturn(sec);
        when(sec.getBoolean("enabled", true)).thenReturn(true);
        List<String> only = Arrays.asList("velocity");
        when(sec.getStringList("checks")).thenReturn(only);
        when(sec.getDouble("min_tps", 18.5)).thenReturn(18.5);
        when(sec.getLong("max_ping_ms", 250L)).thenReturn(250L);

        LagCompensator lc = new LagCompensator(plugin);
        // killaura no esta en allowlist → no se suprime nunca por lag.
        assertFalse(lc.shouldSuppress(mockPlayer(99999), "killaura_aim"));
    }

    private static Player mockPlayer(long ping) {
        Player p = mock(Player.class);
        when(p.getUniqueId()).thenReturn(UUID.randomUUID());
        when(p.getPing()).thenReturn((int) ping);
        return p;
    }
}
