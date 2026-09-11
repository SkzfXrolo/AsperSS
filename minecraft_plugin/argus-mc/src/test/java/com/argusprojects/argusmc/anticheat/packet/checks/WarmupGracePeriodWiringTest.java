package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import com.argusprojects.argusmc.tuning.LagCompensator;
import com.argusprojects.argusmc.tuning.WarmupGracePeriod;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/**
 * Pack 48 round 3 — igual que LagCompensatorWiringTest pero para
 * WarmupGracePeriod (gracia de {@code tuning.warmup.join_grace_ms} /
 * {@code teleport_grace_ms}), otro componente que estaba construido y
 * testeado en aislamiento sin que ningún check lo llamara.
 *
 * <p>LagCompensator se mockea SIN stubear shouldSuppress (Mockito
 * devuelve false por default) para que la ejecución llegue al segundo
 * gate — el que este test verifica.
 */
public class WarmupGracePeriodWiringTest {

    private ArgusPlugin pluginInGrace(String checkName) {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        AnticheatConfig cfg = mock(AnticheatConfig.class);
        when(plugin.getAnticheatConfig()).thenReturn(cfg);
        when(cfg.isCheckEnabled(checkName)).thenReturn(true);

        when(plugin.getLagCompensator()).thenReturn(mock(LagCompensator.class)); // shouldSuppress=false default

        WarmupGracePeriod warmup = mock(WarmupGracePeriod.class);
        when(warmup.inGrace(any(), eq(checkName))).thenReturn(true);
        when(plugin.getWarmupGracePeriod()).thenReturn(warmup);
        return plugin;
    }

    private static Player player() {
        Player p = mock(Player.class);
        when(p.getUniqueId()).thenReturn(UUID.randomUUID());
        return p;
    }

    @Test
    void speedPacketSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("speed_packet");
        ViolationSink sink = mock(ViolationSink.class);
        new SpeedPacketCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, 0L, true, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("speed_packet"));
        verifyNoInteractions(sink);
    }

    @Test
    void velocitySuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("velocity");
        ViolationSink sink = mock(ViolationSink.class);
        new VelocityCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("velocity"));
        verifyNoInteractions(sink);
    }

    @Test
    void jetpackSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("jetpack");
        ViolationSink sink = mock(ViolationSink.class);
        new JetpackCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, 0L, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("jetpack"));
        verifyNoInteractions(sink);
    }

    @Test
    void spiderSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("spider");
        ViolationSink sink = mock(ViolationSink.class);
        new SpiderCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("spider"));
        verifyNoInteractions(sink);
    }

    @Test
    void stepSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("step");
        ViolationSink sink = mock(ViolationSink.class);
        new StepCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, true, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("step"));
        verifyNoInteractions(sink);
    }

    @Test
    void vclipSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("vclip");
        ViolationSink sink = mock(ViolationSink.class);
        new VClipCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("vclip"));
        verifyNoInteractions(sink);
    }

    @Test
    void timerJitterSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("timer_jitter");
        ViolationSink sink = mock(ViolationSink.class);
        new TimerJitterCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0L, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("timer_jitter"));
        verifyNoInteractions(sink);
    }

    @Test
    void antiKnockbackSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("antikb");
        ViolationSink sink = mock(ViolationSink.class);
        new AntiKnockbackCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0L, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("antikb"));
        verifyNoInteractions(sink);
    }

    @Test
    void noSlowSneakSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("noslowsneak");
        ViolationSink sink = mock(ViolationSink.class);
        new NoSlowSneakCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0L, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("noslowsneak"));
        verifyNoInteractions(sink);
    }

    @Test
    void boatFlySuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("boat_fly");
        ViolationSink sink = mock(ViolationSink.class);
        new BoatFlyCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, 0L, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("boat_fly"));
        verifyNoInteractions(sink);
    }

    @Test
    void boatFlyAdvancedSuppressedDuringWarmup() {
        ArgusPlugin plugin = pluginInGrace("boat_fly_advanced");
        ViolationSink sink = mock(ViolationSink.class);
        new BoatFlyAdvancedCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, 0L, sink);
        verify(plugin.getWarmupGracePeriod()).inGrace(any(), eq("boat_fly_advanced"));
        verifyNoInteractions(sink);
    }
}
