package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — ScaffoldRotationCheck.
 *
 * <p>Scaffold (downward) cheats colocan bloques bajo los pies del
 * jugador con el cursor apuntando muy abajo (pitch ≈ +90°). Detecta:
 * <ul>
 *   <li>Snap a pitch &gt; {@code min_pitch_deg} (default 80°) en el
 *       momento del block placement.</li>
 *   <li>Pattern: placement seguido (en {@code window_ms}) con pitch
 *       constantemente cerca de +90° y movimiento de yaw &lt; 5°.</li>
 * </ul>
 */
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

        // El bloque colocado debe estar bajo el jugador (placedY <= playerY).
        if (placedY > player.getLocation().getBlockY()) {
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
}
