package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class NoSlowSneakCheck {

    private final ArgusPlugin plugin;
    private long lastSampleMs;

    public NoSlowSneakCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double nz, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("noslowsneak")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "noslowsneak")) return;
        if (!s.sneakActive) {
            s.noSlowSneakConsec = 0;
            return;
        }
        long dt = now - lastSampleMs;
        if (dt < 30L || dt > 500L) {
            lastSampleMs = now;
            return;
        }
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("noslowsneak");
        double maxBps = sec != null ? sec.getDouble("max_sneak_bps", 1.5) : 1.5;
        int consecMid = sec != null ? sec.getInt("consec_mid", 5) : 5;
        int consecHigh= sec != null ? sec.getInt("consec_high", 10) : 10;

        double dx = nx - s.lastX;
        double dz = nz - s.lastZ;
        double bps = Math.sqrt(dx*dx + dz*dz) * 1000.0 / dt;
        lastSampleMs = now;

        if (bps > maxBps) {
            s.noSlowSneakConsec++;
            if (s.noSlowSneakConsec >= consecHigh) {
                sink.flag(new Violation(player, "noslowsneak_packet",
                    ViolationLevel.HIGH,
                    String.format("sneak bps=%.2f > %.2f x%d", bps, maxBps, s.noSlowSneakConsec)));
                s.noSlowSneakConsec = 0;
            } else if (s.noSlowSneakConsec >= consecMid) {
                sink.flag(new Violation(player, "noslowsneak_packet",
                    ViolationLevel.MID,
                    String.format("sneak bps=%.2f x%d", bps, s.noSlowSneakConsec)));
            }
        } else {
            s.noSlowSneakConsec = 0;
        }
    }
}
