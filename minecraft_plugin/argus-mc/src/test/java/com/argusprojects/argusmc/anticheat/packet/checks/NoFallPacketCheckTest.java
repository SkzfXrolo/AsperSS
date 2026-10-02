package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import com.argusprojects.argusmc.tuning.WarmupGracePeriod;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

public class NoFallPacketCheckTest {

    private static NoFallPacketCheck check() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        AnticheatConfig cfg = mock(AnticheatConfig.class);
        when(plugin.getAnticheatConfig()).thenReturn(cfg);
        when(cfg.isCheckEnabled("nofall_packet")).thenReturn(true);
        when(plugin.getWarmupGracePeriod()).thenReturn(mock(WarmupGracePeriod.class));
        return new NoFallPacketCheck(plugin);
    }

    /** Piso de piedra en y=63 (se para en y=64); aire en todo lo demas. */
    private static Player player() {
        Block air = mock(Block.class);   when(air.getType()).thenReturn(Material.AIR);
        Block stone = mock(Block.class); when(stone.getType()).thenReturn(Material.STONE);
        World w = mock(World.class);
        when(w.getBlockAt(anyInt(), anyInt(), anyInt())).thenAnswer(i -> ((int) i.getArgument(1)) == 63 ? stone : air);
        when(w.getBlockAt(any(Location.class))).thenReturn(air);
        Player p = mock(Player.class);
        when(p.getWorld()).thenReturn(w);
        when(p.getGameMode()).thenReturn(GameMode.SURVIVAL);
        return p;
    }

    private static void fall(NoFallPacketCheck c, Player p, ViolationSink sink, boolean spoof) {
        PacketDataStore.State s = new PacketDataStore.State();
        double y = 79, vy = 0;
        s.lastY = y;
        while (y > 64) {
            vy = (vy - 0.08) * 0.98;
            double ny = Math.max(64, y + vy);
            boolean ground = spoof || ny == 64;
            c.handlePositionPacket(p, s, 0.5, ny, 0.5, ground, sink);
            s.lastY = ny;
            y = ny;
        }
    }

    @Test
    void honestFallDoesNotFlag() {
        ViolationSink sink = mock(ViolationSink.class);
        fall(check(), player(), sink, false);
        verifyNoInteractions(sink);
    }

    @Test
    void spoofedGroundWhileFallingFlags() {
        ViolationSink sink = mock(ViolationSink.class);
        fall(check(), player(), sink, true);
        verify(sink, atLeastOnce()).flag(any());
    }
}
