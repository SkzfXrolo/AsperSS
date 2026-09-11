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

public final class BoatFlyCheck {

    private final ArgusPlugin plugin;

    public BoatFlyCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("boat_fly")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "boat_fly")) return;
        if (!player.isInsideVehicle()) return;
        if (!(player.getVehicle() instanceof Boat boat)) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("boat_fly");
        long sustainedMs = sec != null ? sec.getLong("sustained_ms", 1500L) : 1500L;
        double minDyTotal = sec != null ? sec.getDouble("min_dy_total", 1.0) : 1.0;

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

        }
    }
}
