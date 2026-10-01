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

public final class SpiderCheck {

    private final ArgusPlugin plugin;

    public SpiderCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("spider")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "spider")) return;
        if (plugin.getWarmupGracePeriod().inGrace(player, "spider")) return;
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.isGliding() || player.isFlying() || player.isInsideVehicle()) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("spider");
        double minDy = sec != null ? sec.getDouble("min_dy", 0.06) : 0.06;
        // Ventana (no ticks seguidos): trepar 1 bloque a 0.3/tick son solo 2-3 ticks imposibles.
        int hitsMid  = sec != null ? sec.getInt("hits_mid", 3) : 3;
        int hitsHigh = sec != null ? sec.getInt("hits_high", 6) : 6;
        long window  = sec != null ? sec.getLong("window_ms", 4000L) : 4000L;
        long now = System.currentTimeMillis();

        Location loc = player.getLocation();
        Material at = loc.getBlock().getType();
        if (at == Material.LADDER || at == Material.VINE || at == Material.SCAFFOLDING
            || at == Material.WATER || at == Material.LAVA || at == Material.POWDER_SNOW
            || at == Material.TWISTING_VINES || at == Material.WEEPING_VINES
            || at == Material.TWISTING_VINES_PLANT || at == Material.WEEPING_VINES_PLANT) {
            s.spiderConsec = 0;
            return;
        }

        // Saltar pegado a una pared es vanilla: la subida decae con la gravedad
        // (vy' = (vy - 0.08) * 0.98). Trepar sin que decaiga no.
        double dy = ny - s.lastY;
        double expected = (s.lastDeltaY - 0.08) * 0.98;
        if (dy < minDy || s.lastOnGround || dy <= expected + 0.03
            || now - s.lastDamageTakenMs < 1_500L || !hasAdjacentWall(loc)) {
            return;
        }

        if (now - s.spiderWindowStartMs > window) {
            s.spiderWindowStartMs = now;
            s.spiderConsec = 0;
        }
        s.spiderConsec++;
        if (s.spiderConsec >= hitsHigh) {
            sink.flag(new Violation(player, "spider_packet",
                ViolationLevel.HIGH,
                String.format("dy>=%.2f con pared adyacente x%d", minDy, s.spiderConsec)));
            s.spiderConsec = 0;
        } else if (s.spiderConsec >= hitsMid) {
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
