package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class InvalidRotationCheck {

    private final ArgusPlugin plugin;

    public InvalidRotationCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s,
                               float yaw, float pitch, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("invalid_rotation")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("invalid_rotation");
        double maxPitch       = sec != null ? sec.getDouble("max_abs_pitch",       90.1)      : 90.1;
        double extremeYawAbs  = sec != null ? sec.getDouble("extreme_abs_yaw",     100_000.0) : 100_000.0;

        if (!Float.isFinite(yaw) || !Float.isFinite(pitch)) {
            sink.flag(new Violation(player, "invalid_rotation_packet",
                ViolationLevel.CRITICAL,
                "non-finite yaw=" + yaw + " pitch=" + pitch));
            return;
        }
        if (Math.abs(pitch) > maxPitch) {
            sink.flag(new Violation(player, "invalid_rotation_packet",
                ViolationLevel.HIGH,
                String.format("pitch=%.2f out of [-%.1f, +%.1f]", pitch, maxPitch, maxPitch)));
        }
        if (Math.abs(yaw) > extremeYawAbs) {
            sink.flag(new Violation(player, "invalid_rotation_packet",
                ViolationLevel.MID,
                String.format("yaw=%.2f extreme (>%.0f)", yaw, extremeYawAbs)));
        }
    }
}
