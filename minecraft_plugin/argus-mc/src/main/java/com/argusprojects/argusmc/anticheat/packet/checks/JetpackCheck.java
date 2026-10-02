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
        if (plugin.getWarmupGracePeriod().inGrace(player, "jetpack")) return;

        MovementContext ctx = MovementContext.snapshotAt(player, nx, ny, nz);
        if (ctx.isLegitFlightLike()) {
            s.jetpackConsec = 0;
            return;
        }
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("jetpack");
        double minDy     = sec != null ? sec.getDouble("min_dy", 0.05) : 0.05;
        double tolerance = sec != null ? sec.getDouble("gravity_tolerance", 0.03) : 0.03;
        int    consecMid = sec != null ? sec.getInt("consec_mid", 4) : 4;
        int    consecHigh= sec != null ? sec.getInt("consec_high", 7) : 7;

        // En el aire vanilla aplica vy' = (vy - 0.08) * 0.98 cada tick: cualquier subida
        // legitima (salto, jump boost, slime, cama, knockback) decae. Subir sin decaer no.
        double dy = ny - s.lastY;
        double expected = (s.lastDeltaY - 0.08) * 0.98;
        boolean defiesGravity = dy >= minDy && dy > expected + tolerance && !s.lastOnGround;
        if (defiesGravity) {
            s.jetpackConsec++;
            if (s.jetpackConsec >= consecHigh) {
                sink.flag(new Violation(player, "jetpack_packet",
                    ViolationLevel.HIGH,
                    String.format("sube sin gravedad dy=%.3f esperado<=%.3f x%d", dy, expected, s.jetpackConsec)));
                s.jetpackConsec = 0;
            } else if (s.jetpackConsec >= consecMid) {
                sink.flag(new Violation(player, "jetpack_packet",
                    ViolationLevel.MID,
                    String.format("sube sin gravedad dy=%.3f esperado<=%.3f x%d", dy, expected, s.jetpackConsec)));
            }
        } else {
            s.jetpackConsec = 0;
        }
    }
}
