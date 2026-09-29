package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import com.argusprojects.argusmc.tuning.LagCompensator;
import org.bukkit.entity.Player;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

/**
 * Pack 48 round 3 — LagCompensator estaba construido (y con sus propios
 * tests unitarios) pero ningún check lo llamaba: quedó como código muerto.
 * Esta prueba confirma que los 11 checks marcados lag-sensitive en
 * config.yml::tuning.lag_compensation.checks (speed_packet, velocity,
 * jetpack, spider, step, vclip, timer_jitter, antikb, noslowsneak,
 * boat_fly, boat_fly_advanced) consultan el gate ANTES de flagear.
 *
 * <p>Cada test verifica DOS cosas: que shouldSuppress() fue efectivamente
 * llamado con el checkName correcto (prueba directa del wiring — no
 * depende de que el resto del método también hubiera retornado solo por
 * los datos default del mock) y que, devolviendo true, no se llega a
 * sink.flag(...).
 */
public class LagCompensatorWiringTest {

    private ArgusPlugin pluginSuppressing(String checkName) {
        ArgusPlugin plugin = mock(ArgusPlugin.class);
        AnticheatConfig cfg = mock(AnticheatConfig.class);
        when(plugin.getAnticheatConfig()).thenReturn(cfg);
        when(cfg.isCheckEnabled(checkName)).thenReturn(true);

        LagCompensator lag = mock(LagCompensator.class);
        when(lag.shouldSuppress(any(), eq(checkName))).thenReturn(true);
        when(plugin.getLagCompensator()).thenReturn(lag);
        return plugin;
    }

    private static Player player() {
        Player p = mock(Player.class);
        when(p.getUniqueId()).thenReturn(UUID.randomUUID());
        return p;
    }

    @Test
    void speedPacketSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("speed_packet");
        ViolationSink sink = mock(ViolationSink.class);
        new SpeedPacketCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, 0L, true, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("speed_packet"));
        verifyNoInteractions(sink);
    }

    @Test
    void velocitySuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("velocity");
        ViolationSink sink = mock(ViolationSink.class);
        new VelocityCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("velocity"));
        verifyNoInteractions(sink);
    }

    @Test
    void jetpackSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("jetpack");
        ViolationSink sink = mock(ViolationSink.class);
        new JetpackCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, 0L, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("jetpack"));
        verifyNoInteractions(sink);
    }

    @Test
    void spiderSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("spider");
        ViolationSink sink = mock(ViolationSink.class);
        new SpiderCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("spider"));
        verifyNoInteractions(sink);
    }

    @Test
    void stepSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("step");
        ViolationSink sink = mock(ViolationSink.class);
        new StepCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, true, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("step"));
        verifyNoInteractions(sink);
    }

    @Test
    void vclipSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("vclip");
        ViolationSink sink = mock(ViolationSink.class);
        new VClipCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("vclip"));
        verifyNoInteractions(sink);
    }

    @Test
    void timerJitterSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("timer_jitter");
        ViolationSink sink = mock(ViolationSink.class);
        new TimerJitterCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0L, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("timer_jitter"));
        verifyNoInteractions(sink);
    }

    @Test
    void antiKnockbackSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("antikb");
        ViolationSink sink = mock(ViolationSink.class);
        new AntiKnockbackCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0L, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("antikb"));
        verifyNoInteractions(sink);
    }

    @Test
    void noSlowSneakSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("noslowsneak");
        ViolationSink sink = mock(ViolationSink.class);
        new NoSlowSneakCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0L, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("noslowsneak"));
        verifyNoInteractions(sink);
    }

    @Test
    void boatFlySuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("boat_fly");
        ViolationSink sink = mock(ViolationSink.class);
        new BoatFlyCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, 0L, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("boat_fly"));
        verifyNoInteractions(sink);
    }

    @Test
    void boatFlyAdvancedSuppressedUnderLag() {
        ArgusPlugin plugin = pluginSuppressing("boat_fly_advanced");
        ViolationSink sink = mock(ViolationSink.class);
        new BoatFlyAdvancedCheck(plugin).handlePositionPacket(
            player(), new PacketDataStore.State(), 0, 0, 0, 0L, sink);
        verify(plugin.getLagCompensator()).shouldSuppress(any(), eq("boat_fly_advanced"));
        verifyNoInteractions(sink);
    }
}
