package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — MultiVelocityCheck.
 *
 * <p>Generalizacion del {@link VelocityCheck} ya existente: en vez de
 * un solo packet ignorando velocity, cuenta cuantos packets seguidos
 * el cliente ignoro la velocity assignada por el server.
 *
 * <p>Un cheat moderno puede absorber 1 velocity (ej: jugadores cerca de
 * un knockback los kicks NetherTotem) pero seguir absorbiendo es
 * indicativo de KnockbackResist activo o NoKB module.
 */
public final class MultiVelocityCheck {

    private final ArgusPlugin plugin;

    public MultiVelocityCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("multi_velocity")) return;

        // Si no hay velocity activa, reset.
        if (s.serverVelConsumed || s.serverVelAssignedAtMs == 0) {
            s.velocityIgnoredConsec = 0;
            return;
        }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("multi_velocity");
        long windowMs    = sec != null ? sec.getLong("window_ms", 500L) : 500L;
        int consecMid    = sec != null ? sec.getInt("consec_mid", 3) : 3;
        int consecHigh   = sec != null ? sec.getInt("consec_high", 6) : 6;
        double fraction  = sec != null ? sec.getDouble("absorbed_fraction", 0.25) : 0.25;

        long sinceAssigned = System.currentTimeMillis() - s.serverVelAssignedAtMs;
        if (sinceAssigned > windowMs) {
            s.velocityIgnoredConsec = 0;
            return;
        }

        double dx = nx - s.lastX;
        double dy = ny - s.lastY;
        double dz = nz - s.lastZ;

        double assignedMag = Math.sqrt(s.serverVelX * s.serverVelX
            + s.serverVelY * s.serverVelY
            + s.serverVelZ * s.serverVelZ);
        double observedMag = Math.sqrt(dx * dx + dy * dy + dz * dz);
        // El cliente "ignora" si el movimiento observado es muy chico vs lo asignado.
        if (assignedMag > 0.10 && observedMag < assignedMag * fraction) {
            s.velocityIgnoredConsec++;
            if (s.velocityIgnoredConsec >= consecHigh) {
                sink.flag(new Violation(player, "multi_velocity_packet",
                    ViolationLevel.HIGH,
                    String.format("absorbed velocity x%d (assigned=%.2f obs=%.2f)",
                        s.velocityIgnoredConsec, assignedMag, observedMag)));
                s.velocityIgnoredConsec = 0;
                s.serverVelConsumed = true;
            } else if (s.velocityIgnoredConsec >= consecMid) {
                sink.flag(new Violation(player, "multi_velocity_packet",
                    ViolationLevel.MID,
                    String.format("absorbed velocity x%d", s.velocityIgnoredConsec)));
            }
        } else if (observedMag >= assignedMag * fraction) {
            s.velocityIgnoredConsec = 0;
            s.serverVelConsumed = true;
        }
    }
}
