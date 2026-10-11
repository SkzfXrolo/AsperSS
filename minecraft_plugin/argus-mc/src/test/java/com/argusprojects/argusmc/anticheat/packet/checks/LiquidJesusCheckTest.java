package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.inventory.PlayerInventory;
import org.junit.jupiter.api.Test;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.*;

class LiquidJesusCheckTest {

    /** Agua en y=150 (superficie ~150.9), aire arriba. */
    private static Player playerOverWater() {
        World w = mock(World.class);
        when(w.getBlockAt(anyInt(), anyInt(), anyInt())).thenAnswer(inv -> {
            int y = inv.getArgument(1);
            Block b = mock(Block.class);
            when(b.getType()).thenReturn(y <= 150 ? Material.WATER : Material.AIR);
            return b;
        });
        Player p = mock(Player.class);
        when(p.getWorld()).thenReturn(w);
        when(p.getGameMode()).thenReturn(GameMode.SURVIVAL);
        when(p.getInventory()).thenReturn(mock(PlayerInventory.class));
        return p;
    }

    private static ArgusPlugin plugin() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        AnticheatConfig cfg = mock(AnticheatConfig.class);
        when(plugin.getAnticheatConfig()).thenReturn(cfg);
        when(cfg.isCheckEnabled("liquidjesus")).thenReturn(true);
        return plugin;
    }

    @Test
    void bouncingOnTheSurfaceWhileWalkingIsFlagged() {
        LiquidJesusCheck check = new LiquidJesusCheck(plugin());
        Player p = playerOverWater();
        PacketDataStore.State s = new PacketDataStore.State();
        ViolationSink sink = mock(ViolationSink.class);
        double x = 1090.5;
        s.lastX = x; s.lastY = 150.98; s.lastZ = 1132.5;
        for (int t = 0; t < 8; t++) {
            x += 0.22;
            double y = t % 2 == 0 ? 151.08 : 150.98;
            check.handlePositionPacket(p, s, x, y, 1132.5, sink);
            s.lastX = x; s.lastY = y;
        }
        verify(sink, atLeastOnce()).flag(any());
    }

    @Test
    void swimmingWithFeetUnderTheSurfaceIsNotFlagged() {
        LiquidJesusCheck check = new LiquidJesusCheck(plugin());
        Player p = playerOverWater();
        PacketDataStore.State s = new PacketDataStore.State();
        ViolationSink sink = mock(ViolationSink.class);
        double x = 1090.5;
        s.lastX = x; s.lastY = 150.5; s.lastZ = 1132.5;
        for (int t = 0; t < 12; t++) {                 // flota en la superficie: pies ~0.4 bajo el agua
            x += 0.2;
            double y = t % 2 == 0 ? 150.6 : 150.45;
            check.handlePositionPacket(p, s, x, y, 1132.5, sink);
            s.lastX = x; s.lastY = y;
        }
        verify(sink, never()).flag(any());
    }
}
