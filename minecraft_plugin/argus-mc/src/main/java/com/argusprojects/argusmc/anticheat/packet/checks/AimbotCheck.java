package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * Pack 48 round 3 — AimbotCheck.
 *
 * <p>Cuando hay varios enemigos cercanos al atacante y el cliente
 * "snipea" al más lejano ignorando los más cercanos, el patrón es
 * de aimbot priorizando objetivo (closest-target, headshot, etc.).
 *
 * <p>Heurística: en el momento del attack, contar cuántas entidades
 * vivas hay a menor distancia que el target real. Si hay &gt;= 2 más
 * cercanas pero el target está &gt; {@code min_skip_distance} m, flag.
 */
public final class AimbotCheck {

    private final ArgusPlugin plugin;

    public AimbotCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target, PacketDataStore.State s,
                             ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("aimbot")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("aimbot");
        double minSkipDist = sec != null ? sec.getDouble("min_skip_distance", 3.5) : 3.5;
        int    minSkipped  = sec != null ? sec.getInt("min_skipped_targets", 2) : 2;
        int    consecHigh  = sec != null ? sec.getInt("consec_high", 3) : 3;

        Vector pl = player.getEyeLocation().toVector();
        double targetDist = target.getLocation().toVector().distance(pl);
        if (targetDist < minSkipDist) {
            s.aimbotConsec = 0;
            return;
        }

        int closerCount = 0;
        try {
            for (Entity e : player.getWorld().getNearbyEntities(target.getLocation(), 4.0, 4.0, 4.0)) {
                if (!(e instanceof org.bukkit.entity.LivingEntity)) continue;
                if (e == player || e == target) continue;
                double d = e.getLocation().toVector().distance(pl);
                if (d < targetDist - 0.2) closerCount++;
                if (closerCount >= minSkipped) break;
            }
        } catch (Throwable ignored) {
            return;
        }

        if (closerCount >= minSkipped) {
            s.aimbotConsec++;
            if (s.aimbotConsec >= consecHigh) {
                sink.flag(new Violation(player, "aimbot_packet",
                    ViolationLevel.HIGH,
                    String.format("salteo %d entidades cercanas a tirar @ d=%.2f",
                        closerCount, targetDist)));
                s.aimbotConsec = 0;
            } else {
                sink.flag(new Violation(player, "aimbot_packet",
                    ViolationLevel.MID,
                    String.format("salteo %d targets, hit a %.2fm", closerCount, targetDist)));
            }
        } else {
            s.aimbotConsec = 0;
        }
    }
}
