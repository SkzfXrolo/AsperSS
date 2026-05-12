package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * Pack 48 round 3 — KillauraThruWallCheck.
 *
 * <p>Raycast desde el ojo del atacante hacia el centro de la entidad
 * target. Si el rayo atraviesa un bloque sólido antes de llegar al
 * target, el hit es ilegal.
 *
 * <p>Tolerancia: se permite 1 step de margin para no flagear hits a
 * través de esquinas en escaleras / slabs.
 */
public final class KillauraThruWallCheck {

    private final ArgusPlugin plugin;

    public KillauraThruWallCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target, PacketDataStore.State s,
                             ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("killaura_thruwall")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("killaura_thruwall");
        int    consecHigh = sec != null ? sec.getInt("consec_high", 3) : 3;
        double stepSize   = sec != null ? sec.getDouble("ray_step", 0.2) : 0.2;
        int    allowedSolids = sec != null ? sec.getInt("allowed_solids", 0) : 0;

        Location from = player.getEyeLocation();
        Location to   = target.getLocation().add(0, 0.9, 0);
        Vector dir = to.toVector().subtract(from.toVector());
        double dist = dir.length();
        if (dist < 0.1) return;
        dir.normalize();

        int solids = 0;
        double traveled = 0;
        Location cur = from.clone();
        while (traveled < dist) {
            cur.add(dir.clone().multiply(stepSize));
            traveled += stepSize;
            Block b = cur.getBlock();
            if (b.getType().isSolid() && !b.isPassable()) {
                solids++;
                if (solids > allowedSolids) break;
            }
        }

        if (solids > allowedSolids) {
            s.thruWallConsec++;
            if (s.thruWallConsec >= consecHigh) {
                sink.flag(new Violation(player, "killaura_thruwall_packet",
                    ViolationLevel.HIGH,
                    "raycast atraviesa " + solids + " bloques solidos hacia target"));
                s.thruWallConsec = 0;
            } else {
                sink.flag(new Violation(player, "killaura_thruwall_packet",
                    ViolationLevel.MID,
                    "raycast atraviesa " + solids + " bloques"));
            }
        } else {
            s.thruWallConsec = 0;
        }
    }
}
