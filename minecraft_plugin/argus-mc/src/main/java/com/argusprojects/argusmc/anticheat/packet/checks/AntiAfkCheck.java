package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * AntiAFK / bots: patrones que una mano no produce.
 *  - Rotacion exactamente constante tick a tick (mismo delta de yaw/pitch 40 veces seguidas).
 *  - Saltos en el lugar a intervalos identicos (5 intervalos >1.5s con menos de 60ms de diferencia).
 */
public final class AntiAfkCheck {

    private static final int JUMPS = 6;

    private final ArgusPlugin plugin;

    public AntiAfkCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s, float oldYaw, float oldPitch,
                               float yaw, float pitch, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("antiafk")) return;
        double dYaw = ScaffoldSnapCheck.yawDelta(oldYaw, yaw) * Math.signum(yaw - oldYaw);
        double dPitch = pitch - oldPitch;
        boolean same = Math.abs(dYaw) > 0.5
            && Math.abs(dYaw - s.afkLastDYaw) < 1e-3 && Math.abs(dPitch - s.afkLastDPitch) < 1e-3;
        s.afkLastDYaw = dYaw;
        s.afkLastDPitch = dPitch;
        s.afkRotConsec = same ? s.afkRotConsec + 1 : 0;
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("antiafk");
        int need = sec != null ? sec.getInt("constant_rotation_ticks", 40) : 40;
        if (s.afkRotConsec >= need && now - s.afkLastFlagMs > 5_000L) {
            s.afkLastFlagMs = now;
            sink.flag(new Violation(player, "antiafk_packet", ViolationLevel.MID,
                String.format("rotacion identica %d ticks seguidos (%.2f°/tick)", s.afkRotConsec, dYaw)));
        }
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s, double nx, double ny, double nz,
                                     boolean onGround, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("antiafk")) return;
        double dy = ny - s.lastY;
        boolean jumpStart = s.lastOnGround && !onGround && Math.abs(dy - 0.42) < 0.01
            && Math.hypot(nx - s.lastX, nz - s.lastZ) < 0.05;
        if (!jumpStart) return;
        s.afkJumps[s.afkJumpCount % JUMPS] = now;
        s.afkJumpCount++;
        if (s.afkJumpCount < JUMPS || now - s.afkLastFlagMs < 30_000L) return;
        if (!isMetronome(s.afkJumps, s.afkJumpCount)) return;
        s.afkLastFlagMs = now;
        sink.flag(new Violation(player, "antiafk_packet", ViolationLevel.LOW,
            "salta en el lugar a intervalo fijo (" + JUMPS + " saltos)"));
    }

    /** Ultimos JUMPS saltos: intervalos > 1.5s y todos dentro de 60ms entre si. */
    static boolean isMetronome(long[] ring, int count) {
        long min = Long.MAX_VALUE, max = Long.MIN_VALUE;
        for (int i = 1; i < JUMPS; i++) {
            long a = ring[(count - JUMPS + i - 1) % JUMPS], b = ring[(count - JUMPS + i) % JUMPS];
            long d = b - a;
            min = Math.min(min, d);
            max = Math.max(max, d);
        }
        return min > 1_500L && max - min < 60L;
    }
}
