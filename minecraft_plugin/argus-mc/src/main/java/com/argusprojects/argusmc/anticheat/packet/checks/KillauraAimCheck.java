package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

public final class KillauraAimCheck {

    private final ArgusPlugin plugin;

    public KillauraAimCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target, PacketDataStore.State s,
                             long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("killaura_aim")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("killaura_aim");
        double maxMicroJitter = sec != null ? sec.getDouble("max_micro_jitter_deg", 0.05) : 0.05;
        long windowMs         = sec != null ? sec.getLong("window_ms", 250L) : 250L;
        int minRotationSamples= sec != null ? sec.getInt("min_samples", 3) : 3;

        int samples;
        double yawSpread = 0.0;
        double pitchSpread = 0.0;
        synchronized (s) {
            samples = s.recentRotations.size();
            if (samples >= minRotationSamples) {
                float minY = Float.POSITIVE_INFINITY, maxY = Float.NEGATIVE_INFINITY;
                float minP = Float.POSITIVE_INFINITY, maxP = Float.NEGATIVE_INFINITY;
                long  cutoff = now - windowMs;
                int   counted = 0;
                for (PacketDataStore.RotationSample r : s.recentRotations) {
                    if (r.tsMs < cutoff) continue;
                    counted++;
                    if (r.yaw   < minY) minY = r.yaw;
                    if (r.yaw   > maxY) maxY = r.yaw;
                    if (r.pitch < minP) minP = r.pitch;
                    if (r.pitch > maxP) maxP = r.pitch;
                }
                samples = counted;
                yawSpread = maxY - minY;
                pitchSpread = maxP - minP;
            }
        }

        if (samples < minRotationSamples) return;

        double combinedSpread = Math.sqrt(yawSpread * yawSpread + pitchSpread * pitchSpread);
        if (combinedSpread < maxMicroJitter) {
            sink.flag(new Violation(player, "killaura_aim_packet",
                ViolationLevel.HIGH,
                String.format("rotation frozen %d samples spread=%.4f° (<%.3f°)",
                    samples, combinedSpread, maxMicroJitter)));
        }
    }
}
