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
 * Pack 48 round 3 — PhaseClipCheck.
 *
 * <p>Variante más estricta del {@code PhaseCheck} existente. PhaseCheck
 * solo flagea cuando hay un delta atravesando un bloque entre dos
 * packets. Este detecta el caso donde el jugador SE QUEDA dentro de un
 * bloque sólido por más de {@code max_dwell_ms} (lo cual es imposible
 * en vanilla — el server lo "saca" del bloque al colisionar).
 *
 * <p>Útil para detectar Phase-Clip que renderiza al jugador ya
 * dentro del bloque.
 */
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

        Material foot = player.getWorld().getBlockAt((int)nx, (int)ny, (int)nz).getType();
        Material body = player.getWorld().getBlockAt((int)nx, (int)(ny + 1.0), (int)nz).getType();
        boolean stuck = isSolidOccluding(foot) && isSolidOccluding(body);

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
