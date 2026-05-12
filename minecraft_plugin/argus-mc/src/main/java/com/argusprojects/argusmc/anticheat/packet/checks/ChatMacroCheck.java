package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — ChatMacroCheck (anti-bot).
 *
 * <p>Bots de chat / spam farms tienden a:
 * <ul>
 *   <li>Mandar mensajes IDENTICOS multiple veces (vs jugadores que reformulan).</li>
 *   <li>Con intervalos REGULARES (varianza temporal &lt; 50ms).</li>
 * </ul>
 *
 * <p>Heuristica: contar en los ultimos N mensajes cuantos repetidos hay, y
 * medir la varianza de intervalos. Si {@code repeats >= min_repeats} y
 * {@code variance < max_variance_ms}, flag.
 */
public final class ChatMacroCheck {

    private final ArgusPlugin plugin;

    public ChatMacroCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleChat(Player player, PacketDataStore.State s, String message, long now,
                           ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("chat_macro")) return;
        if (message == null || message.length() < 2) return;
        // No analizar comandos
        if (message.startsWith("/")) return;

        s.pushChat(message, now);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("chat_macro");
        int    minRepeats     = sec != null ? sec.getInt("min_repeats", 3) : 3;
        double maxVarianceMs  = sec != null ? sec.getDouble("max_interval_variance_ms", 60.0) : 60.0;

        int repeats = 0;
        long prevTs = -1L;
        double sum = 0, sumSq = 0;
        int n = 0;
        synchronized (s) {
            String last = null;
            for (PacketDataStore.ChatSample c : s.recentChat) {
                if (last != null) {
                    long dt = c.tsMs - prevTs;
                    sum += dt;
                    sumSq += dt * dt;
                    n++;
                }
                if (message.equalsIgnoreCase(c.message)) repeats++;
                last = c.message;
                prevTs = c.tsMs;
            }
        }
        if (repeats < minRepeats || n < 2) return;

        double mean = sum / n;
        double variance = (sumSq / n) - (mean * mean);
        double stddev = Math.sqrt(Math.max(0, variance));

        if (stddev < maxVarianceMs) {
            sink.flag(new Violation(player, "chat_macro_packet",
                ViolationLevel.MID,
                String.format("repeats=%d stddev=%.1fms <%.0fms", repeats, stddev, maxVarianceMs)));
        }
    }
}
