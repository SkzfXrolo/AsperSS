package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class FastBowCheck {

    private final ArgusPlugin plugin;

    public FastBowCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBowShoot(Player player, PacketDataStore.State s,
                               long chargeMs, double force, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("fastbow")) return;
        s.lastBowChargeMs = chargeMs;

        // Paper cuenta la carga en ticks reales: el fastbow aca no da flechas fuertes, da flechas
        // debiles muy seguidas. Vanilla necesita click + 3 ticks de carga + soltar (~4-5 tiros/s tope).
        ConfigurationSection rsec = plugin.getAnticheatConfig().checkSection("fastbow");
        int rateMid  = rsec != null ? rsec.getInt("shots_per_sec_mid", 6) : 6;
        int rateHigh = rsec != null ? rsec.getInt("shots_per_sec_high", 9) : 9;
        long now = System.currentTimeMillis();
        int shots;
        synchronized (s.bowShots) {
            s.bowShots.addLast(now);
            while (!s.bowShots.isEmpty() && now - s.bowShots.peekFirst() > 1_000L) s.bowShots.pollFirst();
            shots = s.bowShots.size();
        }
        if (shots >= rateMid) {
            sink.flag(new Violation(player, "fastbow_packet",
                shots >= rateHigh ? ViolationLevel.HIGH : ViolationLevel.MID,
                shots + " flechas en 1s (vanilla max ~5)"));
            return;
        }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("fastbow");

        long minFullDraw  = sec != null ? sec.getLong("min_full_draw_ms", 900L) : 900L;
        long extremeMs    = sec != null ? sec.getLong("extreme_ms", 500L) : 500L;
        double minForce   = sec != null ? sec.getDouble("min_force", 0.95) : 0.95;

        if (force < minForce) return;
        if (chargeMs < extremeMs) {
            sink.flag(new Violation(player, "fastbow_packet",
                ViolationLevel.HIGH,
                "full-draw en " + chargeMs + "ms (vanilla=1000ms)"));
        } else if (chargeMs < minFullDraw) {
            sink.flag(new Violation(player, "fastbow_packet",
                ViolationLevel.MID,
                "full-draw en " + chargeMs + "ms"));
        }
    }
}
