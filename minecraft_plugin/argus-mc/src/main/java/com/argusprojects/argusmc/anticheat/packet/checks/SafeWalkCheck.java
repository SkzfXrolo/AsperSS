package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.util.NumberConversions;

/**
 * SafeWalk: el cliente frena en el borde como si estuviera agachado, pero sin agacharse.
 * Senal: venia caminando hacia el borde, se detiene y 0.1 bloques mas adelante ya no hay
 * piso bajo el hitbox (se hubiera caido). Un humano sin shift casi nunca frena justo ahi.
 */
public final class SafeWalkCheck {

    private static final double HALF_WIDTH = 0.3;
    private static final double LOOKAHEAD = 0.1;
    private static final long SNEAK_TOGGLE_GRACE_MS = 500L;

    private final ArgusPlugin plugin;

    public SafeWalkCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s, double nx, double ny, double nz,
                                     boolean onGround, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("safewalk")) return;
        double dx = nx - s.lastX, dz = nz - s.lastZ;
        double speed = Math.hypot(dx, dz);
        if (s.packetSneaking || now - s.sneakToggleMs < SNEAK_TOGGLE_GRACE_MS || !onGround || !s.lastOnGround
            || player.isFlying() || player.isInsideVehicle() || player.isGliding()) {
            s.safeWalkPeakMs = 0;
            return;
        }
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("safewalk");
        double minApproach = sec != null ? sec.getDouble("min_approach_speed", 0.15) : 0.15;
        if (speed >= minApproach) {
            s.safeWalkDirX = dx / speed;
            s.safeWalkDirZ = dz / speed;
            s.safeWalkPeakMs = now;
            return;
        }
        // Clientes 1.9+ no mandan posicion si se movieron < 0.03: el paquete de "frenado" puede tardar 1s.
        if (speed > 0.06 || s.safeWalkPeakMs == 0 || now - s.safeWalkPeakMs > 1100) return;
        s.safeWalkPeakMs = 0;

        if (!isEdgeStop(player.getWorld(), nx, ny, nz, s.safeWalkDirX, s.safeWalkDirZ)) return;

        long window = sec != null ? sec.getLong("window_ms", 15000L) : 15000L;
        int mid  = sec != null ? sec.getInt("stops_mid", 3) : 3;
        int high = sec != null ? sec.getInt("stops_high", 6) : 6;
        if (now - s.safeWalkWindowStartMs > window) {
            s.safeWalkWindowStartMs = now;
            s.safeWalkStops = 0;
        }
        s.safeWalkStops++;
        if (s.safeWalkStops >= mid) {
            ViolationLevel lvl = s.safeWalkStops >= high ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "safewalk_packet", lvl,
                String.format("frena al borde sin agacharse x%d en %ds", s.safeWalkStops, window / 1000)));
            if (lvl == ViolationLevel.HIGH) s.safeWalkStops = 0;
        }
    }

    /** Parado sobre piso, sin pared adelante, y 0.1 bloques mas en la direccion de avance ya no hay piso. */
    static boolean isEdgeStop(World w, double x, double y, double z, double dirX, double dirZ) {
        int floorY = NumberConversions.floor(y - 0.01);
        double ax = x + dirX * LOOKAHEAD, az = z + dirZ * LOOKAHEAD;
        return anySolid(w, x, z, floorY)
            && !anySolid(w, ax, az, floorY)
            && !anySolid(w, ax, az, floorY + 1);
    }

    private static boolean anySolid(World w, double cx, double cz, int y) {
        for (int bx = NumberConversions.floor(cx - HALF_WIDTH); bx <= NumberConversions.floor(cx + HALF_WIDTH); bx++) {
            for (int bz = NumberConversions.floor(cz - HALF_WIDTH); bz <= NumberConversions.floor(cz + HALF_WIDTH); bz++) {
                if (w.getBlockAt(bx, y, bz).getType().isSolid()) return true;
            }
        }
        return false;
    }
}
