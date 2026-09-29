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

    @Test
    void freshJoinSuppressesAndLogsToFalsePositiveLogger() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        FileConfiguration cfg = mock(FileConfiguration.class);
        ConfigurationSection sec = mock(ConfigurationSection.class);
        when(plugin.getConfig()).thenReturn(cfg);
        when(cfg.getConfigurationSection("tuning.warmup")).thenReturn(sec);
        when(sec.getBoolean("enabled", true)).thenReturn(true);
        when(sec.getLong("join_grace_ms", 5_000L)).thenReturn(5_000L);
        when(sec.getLong("teleport_grace_ms", 2_000L)).thenReturn(2_000L);
        when(sec.getStringList("affected_checks")).thenReturn(java.util.Collections.emptyList());

        var bootstrap = mock(com.argusprojects.argusmc.anticheat.packet.PacketEventsBootstrap.class);
        var store = new com.argusprojects.argusmc.anticheat.packet.PacketDataStore();
        UUID uuid = UUID.randomUUID();
        var state = store.get(uuid); // crea el State
        state.joinMs = System.currentTimeMillis(); // se acaba de conectar
        when(plugin.getPacketEventsBootstrap()).thenReturn(bootstrap);
        when(bootstrap.getDataStore()).thenReturn(store);

        FalsePositiveLogger fp = mock(FalsePositiveLogger.class);
        when(plugin.getFalsePositiveLogger()).thenReturn(fp);

        WarmupGracePeriod w = new WarmupGracePeriod(plugin);
        Player p = mock(Player.class);
        when(p.getUniqueId()).thenReturn(uuid);

        assertTrue(w.inGrace(p, "speed_packet"));
        verify(fp).record(eq(p), eq("speed_packet"), contains("warmup_join"));
    }
}
