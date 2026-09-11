package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.MovementContext;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class JetpackCheck {

    private final ArgusPlugin plugin;

    public JetpackCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("jetpack")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "jetpack")) return;

        MovementContext ctx = MovementContext.snapshotAt(player, nx, ny, nz);
        if (ctx.isLegitFlightLike()) {
            s.jetpackConsec = 0;
            return;
        }
        if (ctx.jumpBoostAmp >= 3) {
            s.jetpackConsec = 0;
            return;
        }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("jetpack");
        double minDy = sec != null ? sec.getDouble("min_dy", 0.18) : 0.18;
        int    consecMid = sec != null ? sec.getInt("consec_mid", 4) : 4;
        int    consecHigh= sec != null ? sec.getInt("consec_high", 7) : 7;

        double dy = ny - s.lastY;
        if (dy >= minDy && !s.lastOnGround) {
            s.jetpackConsec++;
            if (s.jetpackConsec >= consecHigh) {
                sink.flag(new Violation(player, "jetpack_packet",
                    ViolationLevel.HIGH,
                    String.format("dy>%.2f x%d", minDy, s.jetpackConsec)));
                s.jetpackConsec = 0;
            } else if (s.jetpackConsec >= consecMid) {
                sink.flag(new Violation(player, "jetpack_packet",
                    ViolationLevel.MID,
                    String.format("dy>%.2f x%d", minDy, s.jetpackConsec)));
            }
        } else {
            if (dy <= 0) s.jetpackConsec = 0;
        }
    }
}
