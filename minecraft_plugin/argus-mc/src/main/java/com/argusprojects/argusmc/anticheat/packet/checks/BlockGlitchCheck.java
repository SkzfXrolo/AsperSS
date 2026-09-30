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
        World w = player.getWorld();
        // Se puede clickear cualquier cara visible: solo es glitch si las 6 estan tapadas.
        Material firstBlocker = null;
        int[] firstAt = null;
        for (double[] f : FACE_OFFSETS) {
            double tx = bx + 0.5 + f[0], ty = by + 0.5 + f[1], tz = bz + 0.5 + f[2];
            int[] blocker = firstObstruction(w, eye, tx, ty, tz, bx, by, bz, step, maxRange);
            if (blocker == null) return;
            if (blocker.length == 0) return; // fuera de rango: no se evalua
            if (firstAt == null) {
                firstAt = blocker;
                firstBlocker = w.getBlockAt(blocker[0], blocker[1], blocker[2]).getType();
            }
        }
        sink.flag(new Violation(player, "block_glitch_packet",
            ViolationLevel.HIGH,
            String.format("interact thru %s at (%d,%d,%d)", firstBlocker.name(), firstAt[0], firstAt[1], firstAt[2])));
    }

    /** Centro de cada cara, apenas adentro del bloque para que el rayo termine en la cara. */
    private static final double[][] FACE_OFFSETS = {
        { 0.49, 0, 0}, {-0.49, 0, 0}, {0, 0.49, 0}, {0, -0.49, 0}, {0, 0, 0.49}, {0, 0, -0.49}
    };

    /** null = rayo libre; int[0] = fuera de rango; int[3] = bloque que tapa. */
    private static int[] firstObstruction(World w, Location eye, double tx, double ty, double tz,
                                          int bx, int by, int bz, double step, double maxRange) {
        Vector dir = new Vector(tx - eye.getX(), ty - eye.getY(), tz - eye.getZ());
        double dist = dir.length();
        if (dist <= 0.1 || dist > maxRange) return new int[0];
        dir = dir.normalize();
        double traveled = 0.0;
        while (traveled + step < dist) {
            traveled += step;
            int ix = (int) Math.floor(eye.getX() + dir.getX() * traveled);
            int iy = (int) Math.floor(eye.getY() + dir.getY() * traveled);
            int iz = (int) Math.floor(eye.getZ() + dir.getZ() * traveled);
            if (ix == bx && iy == by && iz == bz) continue;
            Material m = w.getBlockAt(ix, iy, iz).getType();
            if (m.isSolid() && m != Material.AIR && m != Material.WATER && m != Material.LAVA) {
                return new int[]{ix, iy, iz};
            }
        }
        return null;
    }
}
