package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

public final class LiquidWalkCheck {

    private final ArgusPlugin plugin;

    public LiquidWalkCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("liquid_walk")) return;
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.isGliding() || player.isFlying() || player.isInsideVehicle()) {
            s.liquidWalkConsec = 0;
            return;
        }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("liquid_walk");
        int consecMid  = sec != null ? sec.getInt("consec_mid", 6) : 6;
        int consecHigh = sec != null ? sec.getInt("consec_high", 12) : 12;

        if (!s.lastOnGround) {
            s.liquidWalkConsec = 0;
            return;
        }

        Location loc = new Location(player.getWorld(), nx, ny - 0.05, nz);
        Material below = loc.getBlock().getType();
        boolean liquid = below == Material.WATER || below == Material.LAVA;
        if (!liquid) {
            s.liquidWalkConsec = 0;
            return;
        }

        // Parado en el borde de un bloque (la caja mide 0.6: el centro puede quedar sobre el agua)
        // o sobre un nenufar: alguna esquina pisa algo que no es liquido.
        for (double[] c : CORNERS) {
            Material m = new Location(player.getWorld(), nx + c[0], ny - 0.05, nz + c[1]).getBlock().getType();
            Material at = new Location(player.getWorld(), nx + c[0], ny + 0.01, nz + c[1]).getBlock().getType();
            if ((m != Material.WATER && m != Material.LAVA && !m.isAir()) || at == Material.LILY_PAD) {
                s.liquidWalkConsec = 0;
                return;
            }
        }

        if (hasFrostWalker(player) && below == Material.WATER) {
            s.liquidWalkConsec = 0;
            return;
        }

        s.liquidWalkConsec++;
        if (s.liquidWalkConsec >= consecHigh) {
            sink.flag(new Violation(player, "liquid_walk_packet",
                ViolationLevel.HIGH,
                String.format("on-ground sobre %s x%d", below.name(), s.liquidWalkConsec)));
            s.liquidWalkConsec = 0;
        } else if (s.liquidWalkConsec >= consecMid) {
            sink.flag(new Violation(player, "liquid_walk_packet",
                ViolationLevel.MID,
                String.format("on-ground sobre %s x%d", below.name(), s.liquidWalkConsec)));
        }
    }

    private static final double[][] CORNERS = {{0.3, 0.3}, {0.3, -0.3}, {-0.3, 0.3}, {-0.3, -0.3}};

    private boolean hasFrostWalker(Player p) {
        try {
            ItemStack boots = p.getInventory().getBoots();
            if (boots == null) return false;
            return boots.containsEnchantment(Enchantment.FROST_WALKER);
        } catch (Throwable t) {

            try {
                ItemStack boots = p.getInventory().getBoots();
                if (boots == null || boots.getEnchantments().isEmpty()) return false;
                return boots.getEnchantments().keySet().stream()
                    .anyMatch(en -> en.getKey().getKey().equalsIgnoreCase("frost_walker"));
            } catch (Throwable ignored) {}
            return false;
        }
    }
}
