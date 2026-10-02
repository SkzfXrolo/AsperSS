package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.MovementContext;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.util.NumberConversions;

/**
 * Suelo falso (NoFall): el cliente dice onGround=true mientras baja y no hay bloque bajo los pies.
 * El server confia en ese flag para la distancia de caida, asi que Player#getFallDistance()
 * queda en 0 y el check Bukkit de nofall nunca lo ve.
 */
public final class NoFallPacketCheck {

    private static final double HALF_WIDTH = 0.3;

    private final ArgusPlugin plugin;

    public NoFallPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz, boolean claimsGround,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("nofall_packet")) return;
        if (plugin.getWarmupGracePeriod().inGrace(player, "nofall_packet")) return;

        double dy = ny - s.lastY;
        if (!claimsGround || dy > -0.08) {
            if (claimsGround) s.groundSpoofConsec = 0;
            return;
        }
        MovementContext ctx = MovementContext.snapshotAt(player, nx, ny, nz);
        if (ctx.isLegitFlightLike() || ctx.onSlime || ctx.onHoney) {
            s.groundSpoofConsec = 0;
            return;
        }
        if (hasSupport(player.getWorld(), nx, ny, nz)) {
            s.groundSpoofConsec = 0;
            return;
        }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("nofall_packet");
        int consecMid  = sec != null ? sec.getInt("consec_mid", 3) : 3;
        int consecHigh = sec != null ? sec.getInt("consec_high", 8) : 8;

        s.groundSpoofConsec++;
        if (s.groundSpoofConsec >= consecHigh) {
            sink.flag(new Violation(player, "nofall_packet", ViolationLevel.HIGH,
                String.format("onGround falso cayendo dy=%.2f x%d", dy, s.groundSpoofConsec)));
            s.groundSpoofConsec = 0;
        } else if (s.groundSpoofConsec >= consecMid) {
            sink.flag(new Violation(player, "nofall_packet", ViolationLevel.MID,
                String.format("onGround falso cayendo dy=%.2f x%d", dy, s.groundSpoofConsec)));
        }
    }

    /** Algun bloque solido bajo cualquiera de las 4 esquinas de los pies (hasta 0.6 abajo). */
    private static boolean hasSupport(World w, double x, double y, double z) {
        for (double ox : new double[]{-HALF_WIDTH, HALF_WIDTH}) {
            for (double oz : new double[]{-HALF_WIDTH, HALF_WIDTH}) {
                for (double oy : new double[]{-0.05, -0.6}) {
                    Material m = w.getBlockAt(NumberConversions.floor(x + ox),
                        NumberConversions.floor(y + oy), NumberConversions.floor(z + oz)).getType();
                    if (m.isSolid()) return true;
                }
            }
        }
        return false;
    }
}
