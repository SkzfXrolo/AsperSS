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

public final class BoatFlyAdvancedCheck {

    private final ArgusPlugin plugin;

    public BoatFlyAdvancedCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("boat_fly_advanced")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "boat_fly_advanced")) return;
        if (plugin.getWarmupGracePeriod().inGrace(player, "boat_fly_advanced")) return;
        if (!player.isInsideVehicle()) return;
        if (!(player.getVehicle() instanceof Boat boat)) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("boat_fly_advanced");
        long graceMs       = sec != null ? sec.getLong("grace_ms", 300L) : 300L;
        long sustainedMs   = sec != null ? sec.getLong("sustained_ms", 2000L) : 2000L;
        double minHorBpsAir= sec != null ? sec.getDouble("min_horizontal_bps_air", 4.0) : 4.0;

        org.bukkit.Location loc = boat.getLocation();
        Material below = loc.clone().add(0, -0.5, 0).getBlock().getType();
        Material at    = loc.getBlock().getType();
        boolean inWater = below == Material.WATER || at == Material.WATER;
        boolean solid   = below.isSolid();

        if (inWater || solid) {
            s.boatAirSinceMs = 0L;
            s.boatAirStartY  = 0.0;
            return;
        }

        if (s.boatAirSinceMs == 0L) {
            s.boatAirSinceMs = now;
            s.boatAirStartY  = ny;
            return;
        }

        long elapsed = now - s.boatAirSinceMs;
        if (elapsed < graceMs) return;

        org.bukkit.util.Vector v = boat.getVelocity();
        double horizontalBps = Math.sqrt(v.getX() * v.getX() + v.getZ() * v.getZ()) * 20.0;

        if (elapsed >= sustainedMs && horizontalBps >= minHorBpsAir) {
            sink.flag(new Violation(player, "boat_fly_advanced_packet",
                ViolationLevel.HIGH,
                String.format("boat aire %dms hBps=%.2f", elapsed, horizontalBps)));
        }
    }
}
