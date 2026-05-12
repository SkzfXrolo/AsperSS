package com.argusprojects.argusmc.tuning;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

public class WarmupGracePeriodTest {

    @Test
    void disabledReturnsFalse() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        ConfigurationSection sec = mock(ConfigurationSection.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getConfigurationSection("tuning.warmup")).thenReturn(sec);
        when(sec.getBoolean("enabled", true)).thenReturn(false);
        WarmupGracePeriod w = new WarmupGracePeriod(plugin);
        Player p = mock(Player.class);
        when(p.getUniqueId()).thenReturn(UUID.randomUUID());
        assertFalse(w.inGrace(p));
    }

    @Test
    void nullPlayerReturnsFalse() {
        WarmupGracePeriod w = new WarmupGracePeriod(mock(ArgusPlugin.class));
        assertFalse(w.inGrace(null));
    }
}
