package com.argusprojects.argusmc.anticheat.packet;

import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.entity.Player;
import org.bukkit.potion.PotionEffectType;

/**
 * Pack 48 round 2 — contexto de movimiento tick-by-tick para checks Fly/Speed.
 *
 * <p>Centraliza la deteccion de modifiers que afectan velocidad / aceleracion
 * vertical legítimos:
 * <ul>
 *   <li>Water bounce / swimming</li>
 *   <li>Slime / honey / bed bounce</li>
 *   <li>Scaffolding climb / ladder / vine</li>
 *   <li>Soul sand slowdown</li>
 *   <li>Ice / blue_ice acceleration</li>
 *   <li>Speed potion / Slowness</li>
 *   <li>Jump boost / levitation / slow falling</li>
 *   <li>Elytra gliding</li>
 *   <li>Vehicle (boat, minecart, horse)</li>
 *   <li>Creative / spectator</li>
 * </ul>
 *
 * <p>Cada flag se evalua una sola vez por instancia. Es inmutable post-build.
 *
 * <p>USO TIPICO:
 * <pre>
 * MovementContext ctx = MovementContext.snapshot(player, ny);
 * if (ctx.onSlime || ctx.onSlimeJustNow) return; // bounce legitimo
 * </pre>
 */
public final class MovementContext {

    public final Player  player;
    public final boolean creativeOrSpec;
    public final boolean allowFlightAndFlying;
    public final boolean gliding;
    public final boolean swimming;
    public final boolean inWater;
    public final boolean inLava;
    public final boolean onIce;
    public final boolean onSoulSand;
    public final boolean onSlime;
    public final boolean onHoney;
    public final boolean onBed;
    public final boolean onScaffolding;
    public final boolean onLadder;
    public final boolean onVine;
    public final boolean inVehicle;
    public final boolean inBubbleColumn;
    /** Amplifier de Speed potion (-1 si ausente). */
    public final int     speedAmp;
    /** Amplifier de Jump Boost (-1 si ausente). */
    public final int     jumpBoostAmp;
    public final boolean hasLevitation;
    public final boolean hasSlowFalling;
    /** Soul Speed enchantment activa (boots + soul sand/soul soil). */
    public final boolean soulSpeedActive;

    private MovementContext(Player p, Location footLoc) {
        this.player = p;
        GameMode gm = p.getGameMode();
        this.creativeOrSpec = gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR;
        this.allowFlightAndFlying = p.getAllowFlight() && p.isFlying();
        this.gliding = p.isGliding();
        this.swimming = p.isSwimming();
        this.inVehicle = p.isInsideVehicle();

        World w = footLoc.getWorld();
        Material at = w == null ? Material.AIR : footLoc.getBlock().getType();
        Material below = w == null ? Material.AIR : footLoc.clone().add(0, -0.05, 0).getBlock().getType();

        this.inWater = at == Material.WATER || below == Material.WATER || at == Material.BUBBLE_COLUMN;
        this.inLava  = at == Material.LAVA || below == Material.LAVA;
        this.onIce   = isIce(below);
        this.onSoulSand = below == Material.SOUL_SAND || below == Material.SOUL_SOIL;
        this.onSlime = below == Material.SLIME_BLOCK;
        this.onHoney = below == Material.HONEY_BLOCK || at == Material.HONEY_BLOCK;
        this.onBed   = below.name().endsWith("_BED");
        this.onScaffolding = at == Material.SCAFFOLDING || below == Material.SCAFFOLDING;
        this.onLadder = at == Material.LADDER;
        this.onVine   = at == Material.VINE
            || at == Material.TWISTING_VINES || at == Material.WEEPING_VINES
            || at == Material.TWISTING_VINES_PLANT || at == Material.WEEPING_VINES_PLANT;
        this.inBubbleColumn = at == Material.BUBBLE_COLUMN;

        this.speedAmp = ampOf(p, "SPEED");
        int jb = ampOf(p, "JUMP_BOOST");
        if (jb < 0) jb = ampOf(p, "JUMP"); // 1.20 vs 1.21 naming
        this.jumpBoostAmp = jb;
        this.hasLevitation = hasEffect(p, "LEVITATION");
        this.hasSlowFalling = hasEffect(p, "SLOW_FALLING");
        this.soulSpeedActive = onSoulSand && hasSoulSpeedBoots(p);
    }

    /** Snapshot del contexto en la posicion actual del jugador. */
    public static MovementContext snapshot(Player p) {
        return new MovementContext(p, p.getLocation());
    }

    /** Snapshot del contexto en una posicion arbitraria (mas precisa con coords del packet). */
    public static MovementContext snapshotAt(Player p, double x, double y, double z) {
        return new MovementContext(p, new Location(p.getWorld(), x, y, z));
    }

    /**
     * Multiplier estimado de cap de speed horizontal teniendo en cuenta
     * modifiers acumulables. Ej: speed II + ice = base * 1.4 * 1.4 = base * 1.96.
     */
    public double horizontalSpeedMultiplier() {
        double m = 1.0;
        if (speedAmp >= 0)   m *= (1.0 + 0.20 * (speedAmp + 1));
        if (onIce)           m *= 1.4;
        if (soulSpeedActive) m *= 1.4;
        if (onSoulSand && !soulSpeedActive) m *= 0.4;   // ralentiza
        if (onHoney)         m *= 0.5;
        if (inWater && !gliding) m *= 0.6;
        return m;
    }

    /**
     * Multiplier estimado para deltaY positivo (subiendo) que es legitimo.
     */
    public double verticalRiseMultiplier() {
        double m = 1.0;
        if (jumpBoostAmp >= 0) m *= (1.0 + 0.10 * (jumpBoostAmp + 1));
        if (onSlime)           m *= 4.0; // bounce
        if (onBed)             m *= 1.5;
        if (hasLevitation)     m *= 5.0;
        return m;
    }

    /**
     * true si el contexto justifica permitir un check de fly/speed sin flagear.
     * Util para los checks que prefieren "ante la duda, no flagear".
     */
    public boolean isLegitFlightLike() {
        return creativeOrSpec
            || allowFlightAndFlying
            || gliding
            || swimming
            || inWater || inLava
            || onLadder || onVine || onScaffolding
            || hasLevitation
            || hasSlowFalling
            || inBubbleColumn
            || inVehicle;
    }

    // ──────────────────────────────────────────────────────────────────────

    private static boolean isIce(Material m) {
        switch (m) {
            case ICE:
            case PACKED_ICE:
            case BLUE_ICE:
            case FROSTED_ICE:
                return true;
            default:
                return false;
        }
    }

    private static int ampOf(Player p, String typeName) {
        try {
            PotionEffectType t = PotionEffectType.getByName(typeName);
            if (t == null) return -1;
            if (!p.hasPotionEffect(t)) return -1;
            var pe = p.getPotionEffect(t);
            return pe == null ? -1 : pe.getAmplifier();
        } catch (Throwable ignored) {
            return -1;
        }
    }

    private static boolean hasEffect(Player p, String typeName) {
        try {
            PotionEffectType t = PotionEffectType.getByName(typeName);
            return t != null && p.hasPotionEffect(t);
        } catch (Throwable ignored) {
            return false;
        }
    }

    private static boolean hasSoulSpeedBoots(Player p) {
        try {
            var boots = p.getInventory().getBoots();
            if (boots == null || boots.getEnchantments().isEmpty()) return false;
            return boots.getEnchantments().keySet().stream()
                .anyMatch(en -> en.getKey().getKey().equalsIgnoreCase("soul_speed"));
        } catch (Throwable ignored) {
            return false;
        }
    }
}
