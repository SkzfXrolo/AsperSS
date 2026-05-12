package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — FastBowCheck.
 *
 * <p>Full-draw del arco en vanilla son exactamente 20 ticks (1.0s).
 * "FastBow" cheats acortan esto para spammear shots full-damage.
 *
 * <p>Detección: en {@code EntityShootBowEvent} el bridge pasa el
 * {@code chargeMs} (now - lastBowChargeStartMs). Si force es 1.0
 * (full draw) pero chargeMs &lt; {@code min_full_draw_ms} (default
 * 900ms), flag.
 */
public final class FastBowCheck {

    private final ArgusPlugin plugin;

    public FastBowCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBowShoot(Player player, PacketDataStore.State s,
                               long chargeMs, double force, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("fastbow")) return;
        s.lastBowChargeMs = chargeMs;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("fastbow");
        long minFullDraw  = sec != null ? sec.getLong("min_full_draw_ms", 900L) : 900L;
        long extremeMs    = sec != null ? sec.getLong("extreme_ms", 500L) : 500L;
        double minForce   = sec != null ? sec.getDouble("min_force", 0.95) : 0.95;

        if (force < minForce) return; // no full draw, no aplica.
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
