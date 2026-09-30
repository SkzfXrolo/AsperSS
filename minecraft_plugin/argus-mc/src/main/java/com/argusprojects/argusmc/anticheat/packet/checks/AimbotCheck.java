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

import java.util.Collection;

public final class AimbotCheck {

    private final ArgusPlugin plugin;

    public AimbotCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target, Collection<Entity> nearby,
                             PacketDataStore.State s, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("aimbot")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("aimbot");
        double minSkipDist = sec != null ? sec.getDouble("min_skip_distance", 2.0) : 2.0;
        int    minSkipped  = sec != null ? sec.getInt("min_skipped_targets", 1) : 1;
        int    consecHigh  = sec != null ? sec.getInt("consec_high", 3) : 3;

        Vector pl = player.getEyeLocation().toVector();
        double targetDist = target.getLocation().toVector().distance(pl);
        if (targetDist < minSkipDist) {
            s.aimbotConsec = 0;
            return;
        }

        // Vanilla golpea a la PRIMERA entidad que corta el rayo de la mira: pegarle a un objetivo
        // con otra entidad en el medio es imposible. Estar cerca pero al costado no cuenta.
        // Se prueban dos puntos del objetivo (centro y altura de ojos) y hitboxes achicadas
        // para no castigar solapamientos de borde por interpolacion.
        int closerCount = 0;
        org.bukkit.util.BoundingBox tbb;
        try { tbb = target.getBoundingBox(); } catch (Throwable ignored) { return; }
        Vector[] aimPoints = {
            tbb.getCenter(),
            new Vector(tbb.getCenterX(), tbb.getMaxY() - 0.2, tbb.getCenterZ())
        };
        try {
            for (Entity e : nearby) {
                if (!(e instanceof org.bukkit.entity.LivingEntity)) continue;
                if (e == player || e == target || e.getWorld() != target.getWorld()) continue;
                org.bukkit.util.BoundingBox bb = e.getBoundingBox().clone().expand(-0.15);
                boolean blocksAll = true;
                for (Vector aim : aimPoints) {
                    Vector dir = aim.clone().subtract(pl);
                    double len = dir.length();
                    if (len < 0.1 || bb.rayTrace(pl, dir.normalize(), len) == null) {
                        blocksAll = false;
                        break;
                    }
                }
                if (blocksAll && ++closerCount >= minSkipped) break;
            }
        } catch (Throwable ignored) {
            return;
        }

        if (closerCount >= minSkipped) {
            s.aimbotConsec++;
            if (s.aimbotConsec >= consecHigh) {
                sink.flag(new Violation(player, "aimbot_packet",
                    ViolationLevel.HIGH,
                    String.format("golpe a traves de %d entidad(es) @ d=%.2f",
                        closerCount, targetDist)));
                s.aimbotConsec = 0;
            } else {
                sink.flag(new Violation(player, "aimbot_packet",
                    ViolationLevel.MID,
                    String.format("golpe a traves de %d entidad(es) @ d=%.2f", closerCount, targetDist)));
            }
        } else {
            s.aimbotConsec = 0;
        }
    }
}
