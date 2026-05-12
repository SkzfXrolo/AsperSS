package com.argusprojects.argusmc.oracle;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

public class OracleConfigTest {

    @Test
    void defaultsWhenSectionMissing() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getConfigurationSection("oracle")).thenReturn(null);
        OracleConfig oc = OracleConfig.fromPlugin(plugin);
        assertFalse(oc.enabled);
        assertEquals(1500L, oc.timeoutMs);
        assertEquals(0.6, oc.weightFloor, 1e-9);
    }

    @Test
    void parsesAllFields() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        ConfigurationSection sec = mock(ConfigurationSection.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getConfigurationSection("oracle")).thenReturn(sec);
        when(sec.getBoolean("enabled", false)).thenReturn(true);
        when(sec.getString("url", "")).thenReturn("https://oracle.example/eval");
        when(sec.getString("api_key", "")).thenReturn("KEY");
        when(sec.getLong("timeout_ms", 1500L)).thenReturn(2000L);
        when(sec.getLong("cache_ttl_ms", 30_000L)).thenReturn(45_000L);
        when(sec.getDouble("weight_floor", 0.6)).thenReturn(0.5);
        when(sec.getDouble("weight_ceiling", 1.5)).thenReturn(1.8);
        when(sec.getLong("heartbeat_interval_s", 60L)).thenReturn(120L);
        when(sec.getString("heartbeat_url", "")).thenReturn("https://oracle.example/hb");
        OracleConfig oc = OracleConfig.fromPlugin(plugin);
        assertTrue(oc.enabled);
        assertEquals("https://oracle.example/eval", oc.url);
        assertEquals("KEY", oc.apiKey);
        assertEquals(2000L, oc.timeoutMs);
        assertEquals(45_000L, oc.cacheTtlMs);
        assertEquals(0.5, oc.weightFloor, 1e-9);
        assertEquals(1.8, oc.weightCeiling, 1e-9);
        assertEquals(120L, oc.heartbeatIntervalSec);
        assertTrue(oc.hasValidUrl());
    }

    @Test
    void hasValidUrlFalseWhenDisabled() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        ConfigurationSection sec = mock(ConfigurationSection.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getConfigurationSection("oracle")).thenReturn(sec);
        when(sec.getBoolean("enabled", false)).thenReturn(false);
        when(sec.getString("url", "")).thenReturn("https://x");
        when(sec.getString("api_key", "")).thenReturn("K");
        when(sec.getLong("timeout_ms", 1500L)).thenReturn(1500L);
        when(sec.getLong("cache_ttl_ms", 30_000L)).thenReturn(30_000L);
        when(sec.getDouble("weight_floor", 0.6)).thenReturn(0.6);
        when(sec.getDouble("weight_ceiling", 1.5)).thenReturn(1.5);
        when(sec.getLong("heartbeat_interval_s", 60L)).thenReturn(60L);
        when(sec.getString("heartbeat_url", "")).thenReturn("");
        OracleConfig oc = OracleConfig.fromPlugin(plugin);
        assertFalse(oc.hasValidUrl());
    }
}
