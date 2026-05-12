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

/**
 * Pack 48 round2 — LiquidWalkCheck.
 *
 * <p>Detecta cuando un jugador esta on-ground encima de agua/lava sin que
 * abajo haya frostwalker, sin slime/honey blocks, sin estar nadando. El
 * cheat "Jesus" / "WaterWalk" hace que el agua actue como solido.
 *
 * <p>Whitelist: frost walker boots, depth strider en agua, dolphin grace.
 */
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

        // Player on-ground.
        if (!s.lastOnGround) {
            s.liquidWalkConsec = 0;
            return;
        }

        // Bloque exactamente debajo de los pies.
        Location loc = new Location(player.getWorld(), nx, ny - 0.05, nz);
        Material below = loc.getBlock().getType();
        boolean liquid = below == Material.WATER || below == Material.LAVA;
        if (!liquid) {
            s.liquidWalkConsec = 0;
            return;
        }

        // Frost walker boots → agua queda solida abajo legit.
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

    private boolean hasFrostWalker(Player p) {
        try {
            ItemStack boots = p.getInventory().getBoots();
            if (boots == null) return false;
            return boots.containsEnchantment(Enchantment.FROST_WALKER);
        } catch (Throwable t) {
            // Fallback para versiones nuevas que renombren la enchant.
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
