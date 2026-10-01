package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Strafe: cambiar de direccion en el aire conservando la velocidad.
 * Vanilla en el aire: v' = v * 0.91 + input, con |input| <= 0.026 (sprint). Si el desvio contra
 * v * 0.91 supera eso y la velocidad no bajo (no fue un choque contra pared), es imposible.
 */
public final class StrafeCheck {

    private static final double AIR_FRICTION = 0.91;
    private static final double MAX_AIR_ACCEL = 0.026;

    private final ArgusPlugin plugin;

    public StrafeCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s, double nx, double nz,
                                     boolean onGround, long now, ViolationSink sink) {
        double dx = nx - s.lastX, dz = nz - s.lastZ;
        double pdx = s.strafePrevDx, pdz = s.strafePrevDz;
        long dt = now - s.lastMoveMs;
        s.strafePrevDx = dx;
        s.strafePrevDz = dz;
        // Hacen falta 2 ticks seguidos en el aire: el tick del salto suma el impulso de sprint-jump.
        s.strafeAirTicks = onGround ? 0 : s.strafeAirTicks + 1;
        if (!plugin.getAnticheatConfig().isCheckEnabled("strafe")) return;
        if (s.strafeAirTicks < 3 || dt < 30L || dt > 70L || s.teleporting) return;
        if (now - s.lastDamageTakenMs < 1_500L) return;
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.isFlying() || player.isGliding() || player.isInsideVehicle() || player.isInWater()
            || player.isClimbing() || player.isRiptiding()) return;
        Material at = player.getLocation().getBlock().getType();
        if (at == Material.COBWEB || at == Material.LAVA || at == Material.POWDER_SNOW
            || at == Material.SWEET_BERRY_BUSH || at == Material.BUBBLE_COLUMN) return;

        if (!isImpossibleTurn(pdx, pdz, dx, dz)) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("strafe");
        long window = sec != null ? sec.getLong("window_ms", 2000L) : 2000L;
        int mid  = sec != null ? sec.getInt("hits_mid", 4) : 4;
        int high = sec != null ? sec.getInt("hits_high", 8) : 8;
        if (now - s.strafeWindowStartMs > window) {
            s.strafeWindowStartMs = now;
            s.strafeHits = 0;
        }
        s.strafeHits++;
        if (s.strafeHits >= mid) {
            ViolationLevel lvl = s.strafeHits >= high ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "strafe_packet", lvl,
                String.format("gira en el aire sin perder velocidad x%d", s.strafeHits)));
            if (lvl == ViolationLevel.HIGH) s.strafeHits = 0;
        }
    }

    static boolean isImpossibleTurn(double pdx, double pdz, double dx, double dz) {
        double px = pdx * AIR_FRICTION, pz = pdz * AIR_FRICTION;
        double predicted = Math.hypot(px, pz);
        if (predicted < 0.1) return false; // casi quieto: el input domina, no hay nada que medir
        double deviation = Math.hypot(dx - px, dz - pz);
        // Margen x1.5 + 0.01 por redondeo de paquetes; si la velocidad cayo fue un choque, no strafe.
        return deviation > MAX_AIR_ACCEL * 1.5 + 0.01 && Math.hypot(dx, dz) >= predicted - 0.01;
    }
}
