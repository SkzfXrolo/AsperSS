package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * Pack 48 round2 — BlockGlitchCheck.
 *
 * <p>Detecta place/break a un bloque cuyo LineOfSight desde los ojos del
 * jugador esta bloqueado por otro bloque solido. Es el clasico "Scaffold
 * thru walls" / "BreakThruWall".
 *
 * <p>Algoritmo: hacemos un raycast manual eyes → blockCenter en pasos de
 * 0.25; si en algun paso intermedio hay otro bloque solido (y no es el
 * mismo bloque target), flag.
 */
public final class BlockGlitchCheck {

    private final ArgusPlugin plugin;

    public BlockGlitchCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBlockInteract(Player player, PacketDataStore.State s,
                                    int bx, int by, int bz, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("block_glitch")) return;
        if (player.getGameMode() == GameMode.SPECTATOR) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("block_glitch");
        double step      = sec != null ? sec.getDouble("step", 0.25) : 0.25;
        double maxRange  = sec != null ? sec.getDouble("max_range", 6.0) : 6.0;

        Location eye = player.getEyeLocation();
        Vector dir = new Vector(bx + 0.5 - eye.getX(),
                                by + 0.5 - eye.getY(),
                                bz + 0.5 - eye.getZ());
        double dist = dir.length();
        if (dist <= 0.1 || dist > maxRange) return;
        dir = dir.normalize();

        World w = player.getWorld();
        double traveled = 0.0;
        while (traveled + step < dist) {
            traveled += step;
            double px = eye.getX() + dir.getX() * traveled;
            double py = eye.getY() + dir.getY() * traveled;
            double pz = eye.getZ() + dir.getZ() * traveled;
            int ix = (int) Math.floor(px);
            int iy = (int) Math.floor(py);
            int iz = (int) Math.floor(pz);
            if (ix == bx && iy == by && iz == bz) continue; // ya en el target
            Material m = w.getBlockAt(ix, iy, iz).getType();
            if (m.isSolid() && m != Material.AIR && m != Material.WATER && m != Material.LAVA) {
                sink.flag(new Violation(player, "block_glitch_packet",
                    ViolationLevel.HIGH,
                    String.format("interact thru %s at (%d,%d,%d)", m.name(), ix, iy, iz)));
                return;
            }
        }
    }
}
