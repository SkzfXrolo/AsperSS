package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — AutoClickerAdvancedCheck.
 *
 * <p>Va mas alla del CPS bruto: analiza la VARIANZA de los intervalos
 * entre clicks. Humanos tienen jitter natural (stddev &gt; 15ms en CPS
 * normales). Bots/AutoClickers tienen stddev casi cero.
 *
 * <p>Heuristica: ventana de ultimos N clicks; si {@code n >= min_samples}
 * y la stddev del intervalo es &lt; {@code max_stddev_ms} con CPS &gt; 8,
 * flag.
 */
public final class AutoClickerAdvancedCheck {

    private final ArgusPlugin plugin;

    public AutoClickerAdvancedCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, PacketDataStore.State s, long now,
                             ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("autoclicker_advanced")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("autoclicker_advanced");
        int minSamples       = sec != null ? sec.getInt("min_samples", 8) : 8;
        double maxStddevMs   = sec != null ? sec.getDouble("max_stddev_ms", 6.0) : 6.0;
        double extremeStddev = sec != null ? sec.getDouble("extreme_stddev_ms", 2.0) : 2.0;
        int minCps           = sec != null ? sec.getInt("min_cps", 8) : 8;

        double sum = 0, sumSq = 0;
        int n = 0;
        long prev = 0;
        synchronized (s) {
            for (Long t : s.attackTimestamps) {
                if (prev > 0) {
                    long dt = t - prev;
                    sum += dt;
                    sumSq += dt * dt;
                    n++;
                }
                prev = t;
            }
        }
        if (n < minSamples) return;
        double mean = sum / n;
        if (mean <= 0) return;
        double cps = 1000.0 / mean;
        if (cps < minCps) return;
        double variance = (sumSq / n) - (mean * mean);
        double stddev = Math.sqrt(Math.max(0, variance));

        if (stddev <= extremeStddev) {
            sink.flag(new Violation(player, "autoclicker_advanced_packet",
                ViolationLevel.CRITICAL,
                String.format("CPS=%.1f stddev=%.1fms (<=%.0fms)", cps, stddev, extremeStddev)));
        } else if (stddev < maxStddevMs) {
            sink.flag(new Violation(player, "autoclicker_advanced_packet",
                ViolationLevel.HIGH,
                String.format("CPS=%.1f stddev=%.1fms (<%.0fms)", cps, stddev, maxStddevMs)));
        }
    }
}
