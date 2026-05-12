package com.argusprojects.argusmc.tuning;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.configuration.file.FileConfiguration;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import java.util.UUID;
import java.util.logging.Logger;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

public class FalsePositiveLoggerTest {

    @Test
    void recordAddsEntryToBuffer() {
        ArgusPlugin plugin = mockPlugin();
        FalsePositiveLogger l = new FalsePositiveLogger(plugin);
        Player p = mockPlayer();
        l.record(p, "killaura", "lag");
        assertEquals(1, l.snapshot().size());
        assertEquals(1, l.totalLogged());
        assertEquals("killaura", l.snapshot().get(0).checkName);
        assertEquals("lag", l.snapshot().get(0).cause);
    }

    @Test
    void recordIgnoresNullArgs() {
        ArgusPlugin plugin = mockPlugin();
        FalsePositiveLogger l = new FalsePositiveLogger(plugin);
        l.record(null, "x", "y");
        l.record(mockPlayer(), null, "y");
        assertEquals(0, l.snapshot().size());
    }

    @Test
    void recordBoundedByMax() {
        ArgusPlugin plugin = mockPlugin();
        FalsePositiveLogger l = new FalsePositiveLogger(plugin);
        Player p = mockPlayer();
        for (int i = 0; i < FalsePositiveLogger.MAX_CANCELLED + 50; i++) {
            l.record(p, "check_" + i, "cause");
        }
        assertEquals(FalsePositiveLogger.MAX_CANCELLED, l.snapshot().size());
        assertEquals(FalsePositiveLogger.MAX_CANCELLED + 50, l.totalLogged());
    }

    private static ArgusPlugin mockPlugin() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getBoolean("logging.fp_verbose", false)).thenReturn(false);
        when(plugin.getLogger()).thenReturn(Logger.getLogger("test"));
        return plugin;
    }

    private static Player mockPlayer() {
        Player p = mock(Player.class);
        when(p.getName()).thenReturn("Tester");
        when(p.getUniqueId()).thenReturn(UUID.randomUUID());
        return p;
    }
}
