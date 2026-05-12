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
 * Pack 48 round 3 — LiquidJesusCheck.
 *
 * <p>Variante más estricta de {@code LiquidWalkCheck}. Mientras
 * LiquidWalk solo flagea cuando el player tiene {@code onGround=true}
 * sobre agua, este check considera además:
 * <ul>
 *   <li>Player camina con deltaY ≈ 0 sostenido sobre water/lava.</li>
 *   <li>No tiene Frost Walker, no está nadando, no está en boat.</li>
 *   <li>Bloque actual = AIR pero bloque -1 = LIQUID (definitely walking on liquid).</li>
 * </ul>
 */
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

        Material at = player.getWorld().getBlockAt((int)nx, (int)ny, (int)nz).getType();
        Material below = player.getWorld().getBlockAt((int)nx, (int)(ny - 0.1), (int)nz).getType();
        boolean overLiquid = (below == Material.WATER || below == Material.LAVA);
        if (at != Material.AIR || !overLiquid) {
            s.liquidJesusConsec = 0;
            return;
        }

        double dy = ny - s.lastY;
        if (Math.abs(dy) > maxAbsDy) {
            s.liquidJesusConsec = 0;
            return;
        }

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
