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

public final class PhaseClipCheck {

    private final ArgusPlugin plugin;

    public PhaseClipCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz, long now,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("phaseclip")) return;
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.isFlying() || player.isGliding()) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("phaseclip");
        int consecHigh = sec != null ? sec.getInt("consec_high", 4) : 4;

        Material foot = player.getWorld().getBlockAt(NumberConversions.floor(nx), NumberConversions.floor(ny), NumberConversions.floor(nz)).getType();
        Material body = player.getWorld().getBlockAt(NumberConversions.floor(nx), NumberConversions.floor(ny + 1.0), NumberConversions.floor(nz)).getType();
        // Arena/grava que cae encima entierra al jugador sin que haga nada; y quedar quieto
        // adentro de un bloque no es atravesarlo.
        boolean moving = Math.hypot(nx - s.lastX, nz - s.lastZ) > 0.03;
        boolean stuck = moving && !foot.hasGravity() && !body.hasGravity()
            && isSolidOccluding(foot) && isSolidOccluding(body);

        if (stuck) {
            s.phaseConsec++;
            if (s.phaseConsec >= consecHigh) {
                sink.flag(new Violation(player, "phaseclip_packet",
                    ViolationLevel.CRITICAL,
                    "dentro de bloque " + foot.name() + "/" + body.name() + " x" + s.phaseConsec));
                s.phaseConsec = 0;
            }
        } else {
            s.phaseConsec = 0;
        }
    }

    private static boolean isSolidOccluding(Material m) {
        if (m == null) return false;
        if (m == Material.AIR || m == Material.CAVE_AIR || m == Material.VOID_AIR) return false;
        if (m == Material.WATER || m == Material.LAVA) return false;
        return m.isOccluding();
    }
}
