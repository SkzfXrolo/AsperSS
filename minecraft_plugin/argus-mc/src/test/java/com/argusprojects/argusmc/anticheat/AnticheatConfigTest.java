package com.argusprojects.argusmc.anticheat;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class AnticheatConfigTest {

    @Test
    void defaultsAreEnabledWithEnforcement() {
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(cfg.getBoolean(eq("anticheat.enabled"), anyBoolean())).thenReturn(true);
        when(cfg.getBoolean(eq("anticheat.enforcement"), anyBoolean())).thenReturn(true);
        when(cfg.getBoolean(eq("anticheat.report_to_backend"), anyBoolean())).thenReturn(true);
        when(cfg.getBoolean(eq("anticheat.ai_oracle_enabled"), anyBoolean())).thenReturn(true);
        when(cfg.getString(eq("anticheat.discord_webhook_url"), anyString())).thenReturn("");
        when(cfg.getInt(anyString(), anyInt())).thenAnswer(inv -> inv.getArgument(1));

        AnticheatConfig ac = new AnticheatConfig(cfg);
        assertTrue(ac.isEnabled());
        assertTrue(ac.isEnforcement());
        assertEquals(3, ac.getLowAlertAt());
        assertEquals(3, ac.getMidKickAt());
        assertEquals(2, ac.getHighForceSs());
        assertEquals(2, ac.getCriticalBanAt());
        assertEquals(60, ac.getCriticalBanMinutes());
    }

    @Test
    void discordHookEmptyMeansFalse() {
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(cfg.getString(eq("anticheat.discord_webhook_url"), anyString())).thenReturn("");
        when(cfg.getInt(anyString(), anyInt())).thenAnswer(inv -> inv.getArgument(1));
        when(cfg.getBoolean(anyString(), anyBoolean())).thenReturn(true);
        AnticheatConfig ac = new AnticheatConfig(cfg);
        assertFalse(ac.hasDiscordWebhook());
    }

    @Test
    void discordHookSetMeansTrue() {
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(cfg.getString(eq("anticheat.discord_webhook_url"), anyString()))
            .thenReturn("https://discord.com/api/webhooks/xxx");
        when(cfg.getInt(anyString(), anyInt())).thenAnswer(inv -> inv.getArgument(1));
        when(cfg.getBoolean(anyString(), anyBoolean())).thenReturn(true);
        AnticheatConfig ac = new AnticheatConfig(cfg);
        assertTrue(ac.hasDiscordWebhook());
    }

    @Test
    void enforcementOffSuppressesAllPerCheckEnforce() {
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(cfg.getBoolean(eq("anticheat.enabled"), anyBoolean())).thenReturn(true);
        when(cfg.getBoolean(eq("anticheat.enforcement"), anyBoolean())).thenReturn(false);
        when(cfg.getBoolean(eq("anticheat.report_to_backend"), anyBoolean())).thenReturn(true);
        when(cfg.getBoolean(eq("anticheat.ai_oracle_enabled"), anyBoolean())).thenReturn(true);
        when(cfg.getString(eq("anticheat.discord_webhook_url"), anyString())).thenReturn("");
        when(cfg.getInt(anyString(), anyInt())).thenAnswer(inv -> inv.getArgument(1));
        when(cfg.getConfigurationSection(anyString())).thenReturn(null);

        AnticheatConfig ac = new AnticheatConfig(cfg);
        assertFalse(ac.isEnforcementForCheck("any_check"),
            "enforcement global off debe negar todo per-check enforce");
    }

    @Test
    void perCheckLevelOverrideParsedCorrectly() {
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(cfg.getBoolean(anyString(), anyBoolean())).thenReturn(true);
        when(cfg.getString(eq("anticheat.discord_webhook_url"), anyString())).thenReturn("");
        when(cfg.getInt(anyString(), anyInt())).thenAnswer(inv -> inv.getArgument(1));

        ConfigurationSection sec = mock(ConfigurationSection.class);
        when(sec.getString(eq("force_level"), any())).thenReturn("CRITICAL");
        when(cfg.getConfigurationSection(eq("anticheat.checks.reach"))).thenReturn(sec);

        AnticheatConfig ac = new AnticheatConfig(cfg);
        assertEquals(ViolationLevel.CRITICAL, ac.levelOverrideForCheck("reach"));
    }

    @Test
    void perCheckActionCapDefaultsToNull() {
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(cfg.getBoolean(anyString(), anyBoolean())).thenReturn(true);
        when(cfg.getString(eq("anticheat.discord_webhook_url"), anyString())).thenReturn("");
        when(cfg.getInt(anyString(), anyInt())).thenAnswer(inv -> inv.getArgument(1));
        when(cfg.getConfigurationSection(anyString())).thenReturn(null);

        AnticheatConfig ac = new AnticheatConfig(cfg);
        assertNull(ac.actionCapForCheck("foo"));
    }

    @Test
    void checkSectionForUnknownReturnsNull() {
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(cfg.getBoolean(anyString(), anyBoolean())).thenReturn(true);
        when(cfg.getString(anyString(), anyString())).thenReturn("");
        when(cfg.getInt(anyString(), anyInt())).thenAnswer(inv -> inv.getArgument(1));
        AnticheatConfig ac = new AnticheatConfig(cfg);
        assertNull(ac.checkSection("nonexistent_check"));
    }
}
