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

import java.util.List;

public final class TracersCheck {

    private final ArgusPlugin plugin;

    public TracersCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s,
                               List<Player> invisiblePlayers, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("tracers")) return;
        if (invisiblePlayers.isEmpty()) {
            if (s.tracersConsec > 0) s.tracersConsec--;
            return;
        }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("tracers");
        double maxFov = sec != null ? sec.getDouble("max_fov_deg", 5.0) : 5.0;
        double maxDist = sec != null ? sec.getDouble("max_distance", 20.0) : 20.0;
        int consecHigh = sec != null ? sec.getInt("consec_high", 6) : 6;

        Vector look = player.getEyeLocation().getDirection().normalize();
        Vector from = player.getEyeLocation().toVector();

        Entity bestInvisible = null;
        double bestFov = Double.MAX_VALUE;

        try {
            for (Player p2 : invisiblePlayers) {
                if (p2 == player || p2.getWorld() != player.getWorld()) continue;

                Vector dir = p2.getLocation().toVector().subtract(from);
                double d = dir.length();
                if (d > maxDist) continue;
                dir.normalize();
                double dot = Math.max(-1, Math.min(1, look.dot(dir)));
                double fov = Math.toDegrees(Math.acos(dot));
                if (fov < bestFov) {
                    bestFov = fov;
                    bestInvisible = p2;
                }
            }
        } catch (Throwable ignored) {
            return;
        }

        if (bestInvisible != null && bestFov < maxFov) {
            s.tracersConsec++;
            if (s.tracersConsec >= consecHigh) {
                sink.flag(new Violation(player, "tracers_packet",
                    ViolationLevel.MID,
                    String.format("aim a invisible fov=%.2f° d=%.1fm x%d",
                        bestFov, bestInvisible.getLocation().distance(player.getLocation()),
                        s.tracersConsec)));
                s.tracersConsec = 0;
            }
        } else {
            if (s.tracersConsec > 0) s.tracersConsec--;
        }
    }
}
