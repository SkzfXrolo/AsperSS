package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class ScaffoldAimTest {

    private static ScaffoldRotationCheck check() {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        AnticheatConfig cfg = mock(AnticheatConfig.class);
        when(plugin.getAnticheatConfig()).thenReturn(cfg);
        when(cfg.isCheckEnabled("scaffold_aim")).thenReturn(true);
        return new ScaffoldRotationCheck(plugin);
    }

    private static PacketDataStore.State at(double x, double y, double z, float yaw, float pitch) {
        PacketDataStore.State s = new PacketDataStore.State();
        s.lastX = x; s.lastY = y; s.lastZ = z;
        s.lastYaw = s.prevYaw = yaw;
        s.lastPitch = s.prevPitch = pitch;
        return s;
    }

    @Test
    void pillarLookingDownIsFine() {
        ScaffoldRotationCheck c = check();
        ViolationSink sink = mock(ViolationSink.class);
        PacketDataStore.State s = at(10.5, 65.2, 10.5, 0f, 89f);
        for (int i = 0; i < 6; i++) c.handlePlacementAim(mock(Player.class), s, 10.5, 64.0, 10.5, sink);
        verifyNoInteractions(sink);
    }

    @Test
    void placingBehindWhileLookingAheadFlags() {
        ScaffoldRotationCheck c = check();
        ViolationSink sink = mock(ViolationSink.class);
        // mirando a +X (yaw -90) horizontal, clickea la cara este del bloque de atras/abajo
        PacketDataStore.State s = at(10.4, 65.0, 10.5, -90f, 0f);
        for (int i = 0; i < 4; i++) c.handlePlacementAim(mock(Player.class), s, 10.0, 64.5, 10.5, sink);
        verify(sink, atLeastOnce()).flag(any());
    }
}
