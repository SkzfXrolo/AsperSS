package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class VelocityCheck {

    private static final long VELOCITY_WINDOW_MS = 250L;
    private static final double EXPECTED_FRACTION_THRESHOLD = 0.30;

    private final ArgusPlugin plugin;

    public VelocityCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("velocity")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "velocity")) return;
        if (plugin.getWarmupGracePeriod().inGrace(player, "velocity")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("velocity");
        long windowMs    = sec != null ? sec.getLong("window_ms",            VELOCITY_WINDOW_MS)         : VELOCITY_WINDOW_MS;
        double midFrac   = sec != null ? sec.getDouble("fraction_mid_threshold",  EXPECTED_FRACTION_THRESHOLD) : EXPECTED_FRACTION_THRESHOLD;
        double highFrac  = sec != null ? sec.getDouble("fraction_high_threshold", 0.10)                  : 0.10;
        double minVelH   = sec != null ? sec.getDouble("min_significant_velocity", 0.10)                 : 0.10;

        long now = System.currentTimeMillis();
        if (s.serverVelConsumed) return;
        long age = now - s.serverVelAssignedAtMs;
        if (age <= 0 || age > windowMs) return;

        double expectedH = Math.sqrt(s.serverVelX * s.serverVelX + s.serverVelZ * s.serverVelZ);
        if (expectedH < minVelH) {
            s.serverVelConsumed = true;
            return;
        }

        double dx = nx - s.lastX;
        double dz = nz - s.lastZ;
        double actualH = Math.sqrt(dx * dx + dz * dz);

        double fraction = actualH / expectedH;
        s.serverVelConsumed = true;

        if (fraction < midFrac) {
            ViolationLevel lvl = (fraction < highFrac) ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "velocity_packet",
                lvl,
                String.format("expected=%.3f actual=%.3f fraction=%.0f%%", expectedH, actualH, fraction * 100)));
        }
    }
}
