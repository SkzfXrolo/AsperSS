package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 47 — TimerHack.
 *
 * <p>Un cliente vanilla envia ~20 PlayerPosition packets por segundo (cada 50ms).
 * Los hacks de tipo "Timer" alteran el tick rate para enviar mas packets y
 * procesar mas movimiento, ataques o clicks por segundo. Esta diferencia
 * acumulada (medida en una ventana de 1.5s) se llama "balance":
 *
 * <p>balance = (suma_intervalos_reales - n_packets * 50ms)
 *
 * <p>Un valor &lt; -150ms en 1.5s significa que el cliente envio mas packets de los
 * esperados — TimerHack a 1.05x o superior. Toleramos 100ms para compensar
 * jitter de red. NO se ejecuta en el primer segundo tras el join (warmup) ni
 * durante teleports.
 *
 * <p>Es un check de nivel MID — los TimerHack publicos siempre disparan esto.
 */
public final class TimerCheck {

    private static final long DEFAULT_WINDOW_MS = 1_500L;
    private static final long DEFAULT_IDEAL_INTERVAL_MS = 50L;
    private static final long DEFAULT_TOLERANCE_MS = 150L;
    private static final long DEFAULT_HIGH_THRESHOLD_MS = 300L;
    private static final int  DEFAULT_MIN_PACKETS = 10;

    private final ArgusPlugin plugin;

    public TimerCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("timer")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("timer");
        long windowMs       = sec != null ? sec.getLong("window_ms",        DEFAULT_WINDOW_MS)        : DEFAULT_WINDOW_MS;
        long idealMs        = sec != null ? sec.getLong("ideal_interval_ms", DEFAULT_IDEAL_INTERVAL_MS) : DEFAULT_IDEAL_INTERVAL_MS;
        long toleranceMs    = sec != null ? sec.getLong("tolerance_ms",      DEFAULT_TOLERANCE_MS)    : DEFAULT_TOLERANCE_MS;
        long highBalanceMs  = sec != null ? sec.getLong("high_balance_ms",  DEFAULT_HIGH_THRESHOLD_MS): DEFAULT_HIGH_THRESHOLD_MS;
        int  minPackets     = sec != null ? sec.getInt("min_packets",       DEFAULT_MIN_PACKETS)      : DEFAULT_MIN_PACKETS;
        long warmupMs       = sec != null ? sec.getLong("warmup_ms",        2_000L)                   : 2_000L;

        if (now - s.joinMs < warmupMs) return;
        if (s.teleporting && now < s.teleportUntilMs) return;
        if (s.teleporting && now >= s.teleportUntilMs) {
            s.teleporting = false;
        }

        long cutoff;
        int count;
        long oldest;
        synchronized (s) {
            cutoff = now - windowMs;
            count = 0;
            oldest = now;
            for (Long t : s.moveTimestamps) {
                if (t >= cutoff) {
                    count++;
                    if (t < oldest) oldest = t;
                }
            }
        }
        if (count < minPackets) return;

        long expectedMs = count * idealMs;
        long actualMs   = now - oldest;
        long balance    = actualMs - expectedMs; // negativo = cliente envio MAS rapido

        if (balance < -toleranceMs) {
            double ratio = expectedMs > 0 ? (double) expectedMs / actualMs : 1.0;
            ViolationLevel lvl = (balance < -highBalanceMs) ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "timer_packet",
                lvl,
                String.format("packets=%d balance=%dms ratio=%.2fx", count, balance, ratio)));
        }
    }
}
