package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;

/**
 * Autoclicker externo (macro de mouse con delay aleatorio): el cliente procesa los clicks por
 * tick, asi que en milisegundos parece humano. En ticks no: un humano a 10+ CPS mezcla dobles
 * (0 ticks), 1, 2, 3 y pausas; un clicker con delay acotado (ej. 60-100ms) cae SIEMPRE en solo
 * dos valores vecinos (1-2 ticks). Los ticks se cuentan con los paquetes de movimiento del
 * cliente, inmune a la latencia de red.
 */
public final class AutoClickTickCheck {

    public static final int RING = 128;

    private final ArgusPlugin plugin;

    public AutoClickTickCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleSwing(org.bukkit.entity.Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("autoclicker_ticks")) return;
        if (now - s.lastPlaceMs < 80L) return;   // swing de colocar bloque (1.8), no un click
        // Pausa larga o picando bloques (1.8 manda swing cada tick manteniendo click): se reinicia.
        if (now - s.lastSwingTickMs > 1_000L || now - s.lastDigMs < 1_500L) s.swingTickCount = 0;
        s.lastSwingTickMs = now;
        s.swingTicks[s.swingTickCount % RING] = s.clientTicks;
        s.swingTimes[s.swingTickCount % RING] = now;
        s.swingTickCount++;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("autoclicker_ticks");
        int n = sec != null ? sec.getInt("samples", 40) : 40;
        double minCps = sec != null ? sec.getDouble("min_cps", 9.0) : 9.0;
        if (s.swingTickCount < n + 1 || s.swingTickCount % 10 != 0) return;
        if (now - s.lastAutoClickTickFlagMs < 3_000L) return;

        long[] ticks = new long[n + 1];
        long[] times = new long[n + 1];
        for (int i = 0; i <= n; i++) {
            int idx = (s.swingTickCount - 1 - n + i) % RING;
            ticks[i] = s.swingTicks[idx];
            times[i] = s.swingTimes[idx];
        }
        long spanMs = times[n] - times[0];
        long spanTicks = ticks[n] - ticks[0];
        if (spanMs <= 0 || n * 1000.0 / spanMs < minCps) return;
        // El cliente tiene que haber mandado un paquete por tick (1.8 siempre; 1.9+ si se mueve).
        double expectedTicks = spanMs / 50.0;
        if (spanTicks < expectedTicks * 0.8 || spanTicks > expectedTicks * 1.2) return;

        if (!isNarrowTickRhythm(ticks)) return;
        s.lastAutoClickTickFlagMs = now;
        boolean sustained = s.swingTickCount >= n * 2 + 1;
        sink.flag(new Violation(player, "autoclicker_ticks_packet",
            sustained ? ViolationLevel.HIGH : ViolationLevel.MID,
            String.format("%d clicks a %.1f CPS siempre en 2 intervalos de tick vecinos (sin dobles ni pausas)",
                n, n * 1000.0 / spanMs)));
    }

    /** Todos los intervalos (en ticks) caen en dos valores vecinos, y ninguno es 0 (doble click en un tick). */
    static boolean isNarrowTickRhythm(long[] ticks) {
        long min = Long.MAX_VALUE, max = Long.MIN_VALUE;
        for (int i = 1; i < ticks.length; i++) {
            long d = ticks[i] - ticks[i - 1];
            min = Math.min(min, d);
            max = Math.max(max, d);
        }
        return min >= 1 && max - min <= 1;
    }
}
