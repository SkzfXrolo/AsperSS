package com.argusprojects.argusmc.tuning;

import com.argusprojects.argusmc.anticheat.packet.MovementContext;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.entity.Boat;
import org.bukkit.entity.Player;
import org.bukkit.entity.Minecart;
import org.bukkit.entity.AbstractHorse;

/**
 * Pack 48 round 3 — Extensión de {@link MovementContext} con detección
 * de piston push, elytra fireworks boost, riptide trident, slime block
 * bounce con multi-tick y otros casos extremos que generan FPs.
 *
 * <p>Se construye sobre un {@code MovementContext} ya capturado:
 * <pre>
 *   var ctx  = MovementContext.snapshot(player);
 *   var ext  = MovementContextExtended.from(ctx);
 *   if (ext.isPistonPushed()) return; // legit
 * </pre>
 */
public final class MovementContextExtended {

    public final MovementContext base;
    public final boolean inBoat;
    public final boolean inMinecart;
    public final boolean onHorse;
    public final boolean ridingEntity;
    public final boolean riptiding;
    public final boolean elytraBoosting;
    public final boolean pistonNearby;
    public final boolean slimeBounceChain;
    /** TPS estimado del cliente vía interval de movimientos (>= 21 = timer fast). */
    public final double  estimatedClientTickRate;

    private MovementContextExtended(MovementContext base, Player p,
                                    double estimatedTickRate) {
        this.base = base;
        this.ridingEntity = base.inVehicle;
        Object veh = null;
        try { veh = p.getVehicle(); } catch (Throwable ignored) {}
        this.inBoat     = veh instanceof Boat;
        this.inMinecart = veh instanceof Minecart;
        this.onHorse    = veh instanceof AbstractHorse;

        boolean rip = false;
        try { rip = p.isRiptiding(); } catch (Throwable ignored) {}
        this.riptiding = rip;

        // Elytra boost = gliding + recently shot firework
        // Sin acceso al packet de firework usamos heuristica:
        // gliding + altura ganada > 2 blocks en última segunda.
        this.elytraBoosting = base.gliding && p.getFallDistance() < 0.5f
            && p.getVelocity().getY() > 0.5;

        this.pistonNearby = hasPistonNearby(p.getLocation());
        this.slimeBounceChain = base.onSlime; // simple: el chain real lo
        // mantenemos en State.slimeBouncesInWindow, no aquí.
        this.estimatedClientTickRate = estimatedTickRate;
    }

    public static MovementContextExtended from(MovementContext base, Player p) {
        return new MovementContextExtended(base, p, 20.0);
    }

    public static MovementContextExtended from(MovementContext base, Player p,
                                               double estimatedTickRate) {
        return new MovementContextExtended(base, p, estimatedTickRate);
    }

    public boolean isPistonPushed() { return pistonNearby; }
    public boolean isElytraBoosted() { return elytraBoosting; }
    public boolean isRiptiding()    { return riptiding; }
    public boolean isInBoat()       { return inBoat; }

    /**
     * "Combinado": si CUALQUIER caso legitimo aplica, los checks de
     * movement deberian devolverse sin flag.
     */
    public boolean shouldSkipMovementChecks() {
        return base.isLegitFlightLike()
            || pistonNearby
            || riptiding
            || elytraBoosting
            || base.onSlime
            || base.onHoney
            || base.onBed
            || inMinecart
            || onHorse;
    }

    private static boolean hasPistonNearby(Location loc) {
        if (loc.getWorld() == null) return false;
        int bx = loc.getBlockX(), by = loc.getBlockY(), bz = loc.getBlockZ();
        // Buscar piston extendido en un radio 2 cubico. Es O(125) por check,
        // pero solo se llama si MovementContextExtended se construye explicito.
        for (int dx = -2; dx <= 2; dx++)
            for (int dy = -2; dy <= 2; dy++)
                for (int dz = -2; dz <= 2; dz++) {
                    Material m = loc.getWorld().getBlockAt(bx + dx, by + dy, bz + dz).getType();
                    if (m == Material.PISTON_HEAD
                        || m == Material.MOVING_PISTON
                        || m.name().endsWith("_PISTON")) {
                        return true;
                    }
                }
        return false;
    }
}
