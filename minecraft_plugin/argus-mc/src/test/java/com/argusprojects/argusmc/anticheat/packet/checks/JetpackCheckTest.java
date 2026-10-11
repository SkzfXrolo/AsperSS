package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import com.argusprojects.argusmc.tuning.LagCompensator;
import com.argusprojects.argusmc.tuning.WarmupGracePeriod;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

public class JetpackCheckTest {

    private static ArgusPlugin plugin() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        AnticheatConfig cfg = mock(AnticheatConfig.class);
        when(plugin.getAnticheatConfig()).thenReturn(cfg);
        when(cfg.isCheckEnabled("jetpack")).thenReturn(true);
        when(plugin.getLagCompensator()).thenReturn(mock(LagCompensator.class));
        when(plugin.getWarmupGracePeriod()).thenReturn(mock(WarmupGracePeriod.class));
        return plugin;
    }

    private static Player playerInAir() {
        Block air = mock(Block.class);
        when(air.getType()).thenReturn(Material.AIR);
        World w = mock(World.class);
        when(w.getBlockAt(anyInt(), anyInt(), anyInt())).thenReturn(air);
        when(w.getBlockAt(any(org.bukkit.Location.class))).thenReturn(air);
        Player p = mock(Player.class);
        when(p.getWorld()).thenReturn(w);
        when(p.getGameMode()).thenReturn(GameMode.SURVIVAL);
        return p;
    }

    /** Emula lo que hace PacketAnticheatListener despues de correr los checks. */
    private static void feed(JetpackCheck check, Player p, PacketDataStore.State s, ViolationSink sink,
                             double y, boolean onGround) {
        check.handlePositionPacket(p, s, 0, y, 0, 0L, sink);
        s.lastDeltaY = y - s.lastY;
        s.lastY = y;
        s.lastOnGround = onGround;
    }

    @Test
    void jumpBoostTwoJumpDoesNotFlag() {
        JetpackCheck check = new JetpackCheck(plugin());
        Player p = playerInAir();
        PacketDataStore.State s = new PacketDataStore.State();
        ViolationSink sink = mock(ViolationSink.class);
        s.lastY = 64; s.lastOnGround = true;

        double y = 64, vy = 0.42 + 0.1 * 2; // Jump Boost II
        for (int t = 0; t < 12; t++) {
            y += vy;
            feed(check, p, s, sink, y, false);
            vy = (vy - 0.08) * 0.98;
        }
        verifyNoInteractions(sink);
    }

    @Test
    void sustainedRiseFlags() {
        JetpackCheck check = new JetpackCheck(plugin());
        Player p = playerInAir();
        PacketDataStore.State s = new PacketDataStore.State();
        ViolationSink sink = mock(ViolationSink.class);
        s.lastY = 64; s.lastOnGround = true;

        double y = 64;
        for (int t = 0; t < 10; t++) {
            y += 0.15;
            feed(check, p, s, sink, y, false);
        }
        verify(sink, atLeastOnce()).flag(any());
    }
}
