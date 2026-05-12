package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.entity.Player;

/**
 * Pack 47 — InvalidRotationCheck.
 *
 * <p>El cliente vanilla CLAMPEA pitch en [-90, +90] grados antes de mandar
 * el packet. Cualquier valor fuera de ese rango = cliente modificado o
 * inyector packet. Tambien valida que yaw sea finito (no NaN/Infinity, lo
 * cual fue un crash exploit historico).
 *
 * <p>Esta es la check con menos falsos positivos del paquete entero —
 * directo a HIGH.
 */
public final class InvalidRotationCheck {

    private final ArgusPlugin plugin;

    public InvalidRotationCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s,
                               float yaw, float pitch, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("invalid_rotation")) return;

        if (!Float.isFinite(yaw) || !Float.isFinite(pitch)) {
            sink.flag(new Violation(player, "invalid_rotation_packet",
                ViolationLevel.CRITICAL,
                "non-finite yaw=" + yaw + " pitch=" + pitch));
            return;
        }
        if (Math.abs(pitch) > 90.0f + 0.1f) {
            sink.flag(new Violation(player, "invalid_rotation_packet",
                ViolationLevel.HIGH,
                String.format("pitch=%.2f out of [-90, +90]", pitch)));
        }
        // Sanity de yaw — un valor enorme sostenido suele venir de bots.
        if (Math.abs(yaw) > 100_000.0f) {
            sink.flag(new Violation(player, "invalid_rotation_packet",
                ViolationLevel.MID,
                String.format("yaw=%.2f extreme", yaw)));
        }
    }
}
