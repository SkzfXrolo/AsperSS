package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class FastPlaceCheck {

    private final ArgusPlugin plugin;

    public FastPlaceCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBlockPlacement(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("fast_place")) return;
        if (player.getGameMode() == GameMode.CREATIVE) return;

        s.pushPlace(now);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("fast_place");
        int maxPerSec  = sec != null ? sec.getInt("max_per_sec",  12) : 12;
        int maxPerSec2 = sec != null ? sec.getInt("max_per_sec2", 14) : 14;
        int maxPerSec3 = sec != null ? sec.getInt("max_per_sec3", 22) : 22;

        long[] times;
        synchronized (s) {
            times = s.placeTimestamps.stream().mapToLong(Long::longValue).toArray();
        }
        int rhythmMin = sec != null ? sec.getInt("rhythm_samples", 10) : 10;
        // Con cliente 1.8 las colocaciones van por tick: un jitter de ~10/s cae justo cada 2 ticks.
        // Ritmo fijo solo cuenta a 1 por tick (10 seguidas) o, mas lento, 25 identicas seguidas.
        boolean machine = (times.length > rhythmMin && isMachineRhythm(times, rhythmMin) && meanInterval(times, rhythmMin) <= 75)
            || (times.length > 25 && isMachineRhythm(times, 25));
        if (machine && now - s.lastFastPlaceRhythmFlagMs > 2_000L) {
            s.lastFastPlaceRhythmFlagMs = now;
            boolean sustained = times.length > rhythmMin * 2 && isMachineRhythm(times, rhythmMin * 2);
            sink.flag(new Violation(player, "fast_place_packet",
                sustained ? ViolationLevel.HIGH : ViolationLevel.MID,
                String.format("ritmo de maquina: %d colocaciones a intervalo fijo < vanilla", sustained ? rhythmMin * 2 : rhythmMin)));
        }

        int recent = s.recentPlacesWithin(1_000L, now);
        if (recent >= maxPerSec3) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.HIGH,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec3)));
        } else if (recent >= maxPerSec2) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.MID,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec2)));
        } else if (recent >= maxPerSec) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.LOW,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec)));
        }
    }

    /**
     * FastPlace con click mantenido: coloca cada 1-3 ticks a intervalo fijo. Vanilla manteniendo
     * click va cada 4 ticks (200ms); un humano spameando mezcla 50/100/150ms (clicks por tick).
     * Mira los ultimos n intervalos: media < 175ms y desvio < 18ms = no es una mano.
     */
    static double meanInterval(long[] times, int n) {
        return (times[times.length - 1] - times[times.length - 1 - n]) / (double) n;
    }

    static boolean isMachineRhythm(long[] times, int n) {
        if (times.length < n + 1) return false;
        double sum = 0, sum2 = 0;
        for (int i = times.length - n; i < times.length; i++) {
            double dt = times[i] - times[i - 1];
            sum += dt;
            sum2 += dt * dt;
        }
        double mean = sum / n;
        double std = Math.sqrt(Math.max(0, sum2 / n - mean * mean));
        return mean >= 30 && mean < 175 && std < 18;
    }
}
