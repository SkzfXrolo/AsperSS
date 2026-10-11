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
import org.junit.jupiter.api.Test;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.*;

/** (int)-10.3 == -10, pero el bloque del jugador es -11: con truncado se leia el bloque vecino. */
public class PhaseClipCheckTest {

    private static ArgusPlugin plugin() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        AnticheatConfig cfg = mock(AnticheatConfig.class);
        when(plugin.getAnticheatConfig()).thenReturn(cfg);
        when(cfg.isCheckEnabled("phaseclip")).thenReturn(true);
        return plugin;
    }

    /** Todo es STONE salvo la columna x=-11, z=5, que es AIR. */
    private static Player playerNextToWall() {
        Block air = mock(Block.class);
        when(air.getType()).thenReturn(Material.AIR);
        Block stone = mock(Block.class);
        when(stone.getType()).thenReturn(Material.STONE);

        World w = mock(World.class);
        when(w.getBlockAt(anyInt(), anyInt(), anyInt())).thenReturn(stone);
        when(w.getBlockAt(eq(-11), anyInt(), eq(5))).thenReturn(air);

        Player p = mock(Player.class);
        when(p.getWorld()).thenReturn(w);
        when(p.getGameMode()).thenReturn(GameMode.SURVIVAL);
        return p;
    }

    @Test
    void negativeCoordinatesReadTheCorrectBlock() {
        Player p = playerNextToWall();
        PacketDataStore.State s = new PacketDataStore.State();
        ViolationSink sink = mock(ViolationSink.class);
        PhaseClipCheck check = new PhaseClipCheck(plugin());

        for (int i = 0; i < 10; i++) {
            check.handlePositionPacket(p, s, -10.3, 64.0, 5.5, i * 50L, sink);
        }
        verifyNoInteractions(sink);
    }

    @Test
    void actuallyInsideBlockStillFlags() {
        Player p = playerNextToWall();
        PacketDataStore.State s = new PacketDataStore.State();
        ViolationSink sink = mock(ViolationSink.class);
        PhaseClipCheck check = new PhaseClipCheck(plugin());

        for (int i = 0; i < 4; i++) {
            check.handlePositionPacket(p, s, -9.5, 64.0, 5.5, i * 50L, sink);
        }
        verify(sink).flag(any());
    }

    @Test
    void buriedStandingStillDoesNotFlag() {
        Player p = playerNextToWall();
        PacketDataStore.State s = new PacketDataStore.State();
        s.lastX = -9.5; s.lastZ = 5.5;
        ViolationSink sink = mock(ViolationSink.class);
        PhaseClipCheck check = new PhaseClipCheck(plugin());

        for (int i = 0; i < 8; i++) {
            check.handlePositionPacket(p, s, -9.5, 64.0, 5.5, i * 50L, sink);
        }
        verifyNoInteractions(sink);
    }
}
