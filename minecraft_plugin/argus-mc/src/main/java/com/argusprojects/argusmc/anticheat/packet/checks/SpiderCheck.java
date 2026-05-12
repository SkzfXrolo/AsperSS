package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — SpiderCheck (climb paredes sin scaffolding).
 *
 * <p>"Spider" hack: el jugador sube por paredes verticales solidas sin
 * estar en ladder/vine/scaffolding. Detectamos:
 * <ul>
 *   <li>Player NOT on climbable block (ladder/vine/scaffolding).</li>
 *   <li>Player NOT in water/elytra/creative.</li>
 *   <li>dy positivo sostenido (subiendo).</li>
 *   <li>Al menos un bloque solido a 1 bloque de distancia horizontal en alguna direccion (pared al lado).</li>
 * </ul>
 *
 * <p>Si todas estas condiciones se cumplen por consec_high packets seguidos,
 * el jugador esta literalmente trepando una pared.
 */
public final class SpiderCheck {

    private final ArgusPlugin plugin;

    public SpiderCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("spider")) return;
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.isGliding() || player.isFlying() || player.isInsideVehicle()) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("spider");
        double minDy = sec != null ? sec.getDouble("min_dy", 0.06) : 0.06;
        int consecMid = sec != null ? sec.getInt("consec_mid", 5) : 5;
        int consecHigh= sec != null ? sec.getInt("consec_high", 9) : 9;

        Location loc = player.getLocation();
        Material at = loc.getBlock().getType();
        if (at == Material.LADDER || at == Material.VINE || at == Material.SCAFFOLDING
            || at == Material.WATER || at == Material.LAVA
            || at == Material.TWISTING_VINES || at == Material.WEEPING_VINES
            || at == Material.TWISTING_VINES_PLANT || at == Material.WEEPING_VINES_PLANT) {
            s.spiderConsec = 0;
            return;
        }

        double dy = ny - s.lastY;
        if (dy < minDy) {
            s.spiderConsec = 0;
            return;
        }

        if (!hasAdjacentWall(loc)) {
            s.spiderConsec = 0;
            return;
        }

        s.spiderConsec++;
        if (s.spiderConsec >= consecHigh) {
            sink.flag(new Violation(player, "spider_packet",
                ViolationLevel.HIGH,
                String.format("dy>=%.2f con pared adyacente x%d", minDy, s.spiderConsec)));
            s.spiderConsec = 0;
        } else if (s.spiderConsec >= consecMid) {
            sink.flag(new Violation(player, "spider_packet",
                ViolationLevel.MID,
                String.format("dy>=%.2f con pared adyacente x%d", minDy, s.spiderConsec)));
        }
    }

    private boolean hasAdjacentWall(Location loc) {
        Block base = loc.getBlock();
        for (BlockFace f : new BlockFace[]{BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST}) {
            Block rel = base.getRelative(f);
            if (rel.getType().isSolid()) return true;
        }
        return false;
    }
}
