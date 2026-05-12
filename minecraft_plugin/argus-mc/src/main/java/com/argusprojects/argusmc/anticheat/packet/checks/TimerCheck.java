package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
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

    private static final long WINDOW_MS = 1_500L;
    private static final long IDEAL_INTERVAL_MS = 50L;
    private static final long TOLERANCE_MS = 100L;

    private final ArgusPlugin plugin;

    public TimerCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("timer")) return;

        // Warmup: ignorar 2s tras el join (lag de spawn + carga de chunks)
        if (now - s.joinMs < 2_000L) return;
        // Teleport: ignorar la ventana de gracia
        if (s.teleporting && now < s.teleportUntilMs) return;
        if (s.teleporting && now >= s.teleportUntilMs) {
            s.teleporting = false;
        }

        long cutoff;
        int count;
        long oldest;
        synchronized (s) {
            cutoff = now - WINDOW_MS;
            count = 0;
            oldest = now;
            for (Long t : s.moveTimestamps) {
                if (t >= cutoff) {
                    count++;
                    if (t < oldest) oldest = t;
                }
            }
        }
        if (count < 10) return; // datos insuficientes (lag spike, AFK)

        long expectedMs = count * IDEAL_INTERVAL_MS;
        long actualMs   = now - oldest;
        long balance    = actualMs - expectedMs; // negativo = cliente envio MAS rapido

        if (balance < -(TOLERANCE_MS + 50L)) {
            double ratio = expectedMs > 0 ? (double) expectedMs / actualMs : 1.0;
            ViolationLevel lvl = (balance < -300L) ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "timer_packet",
                lvl,
                String.format("packets=%d balance=%dms ratio=%.2fx", count, balance, ratio)));
        }
    }
}
