package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Boat;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — BoatFlyCheck (vehicle fly via boat).
 *
 * <p>El "boat-fly" es un cheat clasico: el jugador monta un boat (que tiene
 * fisicas que ignoran ciertas reglas de fly), y el cheat hace que el boat
 * floate / suba por el aire sin agua debajo ni input legitimo.
 *
 * <p>Heuristica:
 * <ul>
 *   <li>Player isInsideVehicle y vehicle es Boat.</li>
 *   <li>Bloque debajo del boat NO es WATER ni waterlogged.</li>
 *   <li>Boat lleva al menos N ticks sin tocar agua.</li>
 *   <li>Y del boat aumentando, o constante a altura sospechosa.</li>
 * </ul>
 */
public final class BoatFlyCheck {

    private final ArgusPlugin plugin;

    public BoatFlyCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("boat_fly")) return;
        if (!player.isInsideVehicle()) return;
        if (!(player.getVehicle() instanceof Boat boat)) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("boat_fly");
        long sustainedMs = sec != null ? sec.getLong("sustained_ms", 1500L) : 1500L;
        double minDyTotal = sec != null ? sec.getDouble("min_dy_total", 1.0) : 1.0;

        // Verifica el bloque debajo del boat.
        org.bukkit.Location loc = boat.getLocation();
        Material below = loc.clone().add(0, -0.5, 0).getBlock().getType();
        boolean onWaterOrLand = below == Material.WATER
            || below.name().endsWith("_ICE")
            || below.isSolid();

        if (onWaterOrLand) {
            s.boatAirSinceMs = 0L;
            s.boatAirStartY  = 0.0;
            return;
        }

        if (s.boatAirSinceMs == 0L) {
            s.boatAirSinceMs = now;
            s.boatAirStartY  = ny;
            return;
        }

        long airElapsed = now - s.boatAirSinceMs;
        double dyTotal  = ny - s.boatAirStartY;

        if (airElapsed >= sustainedMs && dyTotal >= minDyTotal) {
            sink.flag(new Violation(player, "boat_fly_packet",
                ViolationLevel.HIGH,
                String.format("boat air %dms dyTotal=%.2f", airElapsed, dyTotal)));
            // No reset — un cheater sostenido seguira flageando; el VM tiene su sliding window.
        }
    }
}
