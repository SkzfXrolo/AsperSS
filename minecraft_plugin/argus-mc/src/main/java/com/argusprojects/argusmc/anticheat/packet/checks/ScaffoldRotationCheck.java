package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class ScaffoldRotationCheck {

    private final ArgusPlugin plugin;

    public ScaffoldRotationCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBlockPlacement(Player player, PacketDataStore.State s,
                                     int placedX, int placedY, int placedZ,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("scaffold_rotation")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("scaffold_rotation");
        double minPitch = sec != null ? sec.getDouble("min_pitch_deg", 80.0) : 80.0;
        int  consecMid  = sec != null ? sec.getInt("consec_mid", 4) : 4;
        int  consecHigh = sec != null ? sec.getInt("consec_high", 7) : 7;

        if (placedY > player.getLocation().getBlockY()) {
            s.scaffoldRotConsec = 0;
            return;
        }

        // Pilarear (saltar y poner debajo mirando al piso) es vanilla: sin avance horizontal.
        double minHoriz = sec != null ? sec.getDouble("min_horizontal_move", 0.05) : 0.05;
        if (s.lastHorizMove < minHoriz) {
            s.scaffoldRotConsec = 0;
            return;
        }

        if (Math.abs(s.lastPitch) < minPitch) {
            s.scaffoldRotConsec = 0;
            return;
        }

        s.scaffoldRotConsec++;
        if (s.scaffoldRotConsec >= consecHigh) {
            sink.flag(new Violation(player, "scaffold_rotation_packet",
                ViolationLevel.HIGH,
                String.format("pitch=%.1f° x%d scaffold-down", s.lastPitch, s.scaffoldRotConsec)));
            s.scaffoldRotConsec = 0;
        } else if (s.scaffoldRotConsec >= consecMid) {
            sink.flag(new Violation(player, "scaffold_rotation_packet",
                ViolationLevel.MID,
                String.format("pitch=%.1f° x%d", s.lastPitch, s.scaffoldRotConsec)));
        }
    }

    /**
     * Vanilla solo coloca en la cara que el jugador tiene en la mira: el punto clickeado
     * (bloque + cursor del paquete) tiene que estar cerca de la direccion de la mirada.
     * Se acepta la rotacion actual o la del tick anterior (la rotacion nueva viaja
     * DESPUES del paquete de colocacion).
     */
    public void handlePlacementAim(Player player, PacketDataStore.State s,
                                   double clickX, double clickY, double clickZ, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("scaffold_aim")) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("scaffold_aim");
        double maxAngle = sec != null ? sec.getDouble("max_angle_deg", 75.0) : 75.0;
        int consecMid   = sec != null ? sec.getInt("consec_mid", 2) : 2;
        int consecHigh  = sec != null ? sec.getInt("consec_high", 4) : 4;

        double eyeY = s.lastY + (player.isSneaking() ? 1.27 : 1.62);
        double dx = clickX - s.lastX, dy = clickY - eyeY, dz = clickZ - s.lastZ;
        double len = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (len < 0.5) return;

        double angle = Math.min(angleTo(s.lastYaw, s.lastPitch, dx / len, dy / len, dz / len),
                                angleTo(s.prevYaw, s.prevPitch, dx / len, dy / len, dz / len));
        if (angle <= maxAngle) {
            s.scaffoldAimConsec = 0;
            return;
        }
        s.scaffoldAimConsec++;
        ViolationLevel lvl = s.scaffoldAimConsec >= consecHigh ? ViolationLevel.HIGH
                           : s.scaffoldAimConsec >= consecMid ? ViolationLevel.MID : null;
        if (lvl != null) {
            sink.flag(new Violation(player, "scaffold_aim_packet", lvl,
                String.format("coloca fuera de la mira: %.0f° x%d", angle, s.scaffoldAimConsec)));
            if (lvl == ViolationLevel.HIGH) s.scaffoldAimConsec = 0;
        }
    }

    private static double angleTo(float yawDeg, float pitchDeg, double tx, double ty, double tz) {
        double yaw = Math.toRadians(yawDeg), pitch = Math.toRadians(pitchDeg);
        double lx = -Math.sin(yaw) * Math.cos(pitch);
        double ly = -Math.sin(pitch);
        double lz =  Math.cos(yaw) * Math.cos(pitch);
        double dot = Math.max(-1.0, Math.min(1.0, lx * tx + ly * ty + lz * tz));
        return Math.toDegrees(Math.acos(dot));
    }
}
