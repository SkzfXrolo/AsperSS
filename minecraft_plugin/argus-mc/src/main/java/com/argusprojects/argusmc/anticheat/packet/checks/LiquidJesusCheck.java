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
import org.bukkit.util.NumberConversions;

public final class LiquidJesusCheck {

    private final ArgusPlugin plugin;

    public LiquidJesusCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("liquidjesus")) return;
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.isFlying() || player.isGliding() || player.isInsideVehicle()) return;
        if (player.isSwimming()) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("liquidjesus");
        int consecMid  = sec != null ? sec.getInt("consec_mid", 4) : 4;
        int consecHigh = sec != null ? sec.getInt("consec_high", 8) : 8;
        double maxAbsDy = sec != null ? sec.getDouble("max_abs_dy", 0.05) : 0.05;

        // Jesus en cualquier modo (solido o "rebote"): los pies se sostienen en/sobre la superficie
        // mientras avanza. Nadando legit se flota con los pies ~0.6 por debajo de la superficie.
        // Paquete repetido sin movimiento: no aporta ni corta la racha.
        if (Math.abs(nx - s.lastX) < 1e-4 && Math.abs(nz - s.lastZ) < 1e-4 && Math.abs(ny - s.lastY) < 1e-4) return;
        // Superficie real de la columna: el bloque de agua mas alto en los pies (o justo debajo).
        // Nadando arriba en vanilla se flota con los pies ~0.4 bajo la superficie; con Jesus quedan encima.
        org.bukkit.World w = player.getWorld();
        int bx = NumberConversions.floor(nx), bz = NumberConversions.floor(nz), fy = NumberConversions.floor(ny);
        int by = isLiquid(w.getBlockAt(bx, fy, bz).getType()) ? fy : fy - 1;
        while (isLiquid(w.getBlockAt(bx, by + 1, bz).getType())) by++;
        Material liquid = w.getBlockAt(bx, by, bz).getType();
        Material at = w.getBlockAt(bx, fy, bz).getType();
        boolean overLiquid = isLiquid(liquid);
        boolean surface = ny >= by + 0.8 && ny <= by + 1.35;
        boolean moving = Math.hypot(nx - s.lastX, nz - s.lastZ) > 0.08;
        if (!overLiquid || !surface || !moving || (at != Material.AIR && at != Material.WATER && at != Material.LAVA)
            || Math.abs(ny - s.lastY) > 0.25) {
            s.liquidJesusConsec = 0;
            return;
        }
        Material below = liquid;

        if (hasFrostWalker(player)) {
            s.liquidJesusConsec = 0;
            return;
        }

        s.liquidJesusConsec++;
        if (s.liquidJesusConsec >= consecHigh) {
            sink.flag(new Violation(player, "liquidjesus_packet",
                ViolationLevel.HIGH,
                "caminando sobre " + below.name() + " x" + s.liquidJesusConsec));
            s.liquidJesusConsec = 0;
        } else if (s.liquidJesusConsec >= consecMid) {
            sink.flag(new Violation(player, "liquidjesus_packet",
                ViolationLevel.MID,
                "sobre " + below.name() + " x" + s.liquidJesusConsec));
        }
    }

    private static boolean isLiquid(Material m) {
        return m == Material.WATER || m == Material.LAVA;
    }

    private static boolean hasFrostWalker(Player p) {
        try {
            var boots = p.getInventory().getBoots();
            if (boots == null) return false;
            return boots.getEnchantments().keySet().stream()
                .anyMatch(e -> e.getKey().getKey().equalsIgnoreCase("frost_walker"));
        } catch (Throwable ignored) {
            return false;
        }
    }
}
