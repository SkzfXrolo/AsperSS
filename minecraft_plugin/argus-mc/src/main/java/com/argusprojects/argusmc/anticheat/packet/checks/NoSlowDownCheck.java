package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.MovementContext;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class NoSlowDownCheck {

    /** Tras un golpe el knockback empuja aunque este comiendo o bloqueando. */
    private static final long DAMAGE_GRACE_MS = 1000L;

    private final ArgusPlugin plugin;

    public NoSlowDownCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double nz, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("noslowdown")) return;
        // Estado real del server: true solo mientras el item se esta usando (comer, arco, escudo...).
        // Block-hit / empezar a comer corriendo: el impulso del sprint tarda unos ticks en caer.
        if (!player.isHandRaised() || now - s.lastDamageTakenMs < DAMAGE_GRACE_MS
            || now - s.useItemStartMs < 300L) {
            s.noSlowDownConsec = 0;
            s.noSlowDownLastMs = now;
            return;
        }
        MovementContext ctx = MovementContext.snapshotAt(player, nx, s.lastY, nz);
        if (ctx.onIce || ctx.isLegitFlightLike()) {
            s.noSlowDownConsec = 0;
            s.noSlowDownLastMs = now;
            return;
        }
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("noslowdown");
        double maxBps = (sec != null ? sec.getDouble("max_horizontal_bps", 4.0) : 4.0)
            * Math.max(1.0, ctx.horizontalSpeedMultiplier());
        int consecMid  = sec != null ? sec.getInt("consec_mid", 3) : 3;
        int consecHigh = sec != null ? sec.getInt("consec_high", 6) : 6;

        long dt = now - s.noSlowDownLastMs;
        s.noSlowDownLastMs = now;
        if (dt < 30L || dt > 500L) return;

        double dx = nx - s.lastX;
        double dz = nz - s.lastZ;
        double bps = Math.sqrt(dx * dx + dz * dz) * 1000.0 / dt;
        if (bps > maxBps) {
            s.noSlowDownConsec++;
            if (s.noSlowDownConsec >= consecHigh) {
                sink.flag(new Violation(player, "noslowdown_packet",
                    ViolationLevel.HIGH,
                    String.format("usando item bps=%.2f (max=%.2f) x%d", bps, maxBps, s.noSlowDownConsec)));
                s.noSlowDownConsec = 0;
            } else if (s.noSlowDownConsec >= consecMid) {
                sink.flag(new Violation(player, "noslowdown_packet",
                    ViolationLevel.MID,
                    String.format("usando item bps=%.2f", bps)));
            }
        } else {
            s.noSlowDownConsec = 0;
        }
    }
}
