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
        handleBlockInteract(player, s, bx, by, bz, null, sink);
    }

    /** clicked = punto exacto del cursor (bloque + cursor del paquete), o null si no viene. */
    public void handleBlockInteract(Player player, PacketDataStore.State s,
                                    int bx, int by, int bz, double[] clicked, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("block_glitch")) return;
        if (player.getGameMode() == GameMode.SPECTATOR) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("block_glitch");
        double step      = sec != null ? sec.getDouble("step", 0.25) : 0.25;
        double maxRange  = sec != null ? sec.getDouble("max_range", 6.0) : 6.0;

        Location feet = player.getLocation();
        World w = player.getWorld();
        double[][] targets = new double[FACE_OFFSETS.length + (clicked != null ? 1 : 0)][];
        for (int i = 0; i < FACE_OFFSETS.length; i++) {
            targets[i] = new double[]{bx + 0.5 + FACE_OFFSETS[i][0], by + 0.5 + FACE_OFFSETS[i][1], bz + 0.5 + FACE_OFFSETS[i][2]};
        }
        if (clicked != null) targets[FACE_OFFSETS.length] = clicked;
        // Es glitch solo si NINGUN rayo (cualquier altura de ojo x cualquier punto visible) llega.
        // Varias alturas porque el ojo agachado difiere por version (1.8: 1.54, 1.14+: 1.27).
        int[] firstAt = null;
        for (double eyeH : EYE_HEIGHTS) {
            Location eye = feet.clone().add(0, eyeH, 0);
            for (double[] t : targets) {
                int[] blocker = firstObstruction(w, eye, t[0], t[1], t[2], bx, by, bz, step, maxRange);
                if (blocker == null || blocker.length == 0) return; // visible, o fuera de rango
                if (firstAt == null) firstAt = blocker;
            }
        }
        Material firstBlocker = w.getBlockAt(firstAt[0], firstAt[1], firstAt[2]).getType();
        sink.flag(new Violation(player, "block_glitch_packet",
            ViolationLevel.HIGH,
            String.format("interact thru %s at (%d,%d,%d)", firstBlocker.name(), firstAt[0], firstAt[1], firstAt[2])));
    }

    private static final double EDGE_TOLERANCE = 0.1;
    private static final double[] EYE_HEIGHTS = {1.62, 1.54, 1.27};

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
            // Rayo que roza una arista/esquina: la muestra discreta cae apenas adentro. No cuenta.
            double px = eye.getX() + dir.getX() * traveled - ix;
            double py = eye.getY() + dir.getY() * traveled - iy;
            double pz = eye.getZ() + dir.getZ() * traveled - iz;
            if (Math.min(Math.min(px, 1 - px), Math.min(Math.min(py, 1 - py), Math.min(pz, 1 - pz))) < EDGE_TOLERANCE) continue;
            Material m = w.getBlockAt(ix, iy, iz).getType();
            // Solo tapa un cubo completo: puertas, trampillas, vallas y losas tienen huecos por donde se clickea.
            if (m.isOccluding()) {
                return new int[]{ix, iy, iz};
            }
        }
        return null;
    }
}
