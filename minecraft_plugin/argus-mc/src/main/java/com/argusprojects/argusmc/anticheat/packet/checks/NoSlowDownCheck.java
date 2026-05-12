package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — NoSlowDownCheck.
 *
 * <p>Cuando el jugador está usando un item (comer, beber poción,
 * cargar bow, levantar escudo) Mojang aplica un slow del ~80%. Los
 * cheats "NoSlow" omiten ese slowdown y siguen moviéndose a velocidad
 * normal.
 *
 * <p>Detección:
 * <ul>
 *   <li>{@code s.useItemStartMs > 0} (item en uso, set por bridge).</li>
 *   <li>velocidad horizontal observada &gt;= {@code max_horizontal_bps}
 *       (default 4.0 b/s — sneaking sin slow es ~4.32, walking-slowed
 *       sin sprint deberia ser &lt;1.5).</li>
 *   <li>3 packets consecutivos así → MID, 6 → HIGH.</li>
 * </ul>
 */
public final class NoSlowDownCheck {

    private final ArgusPlugin plugin;
    private int consec;
    private long lastCheckMs;
    private double cumDx, cumDz;
    private long cumDtMs;

    public NoSlowDownCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double nz, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("noslowdown")) return;
        if (s.useItemStartMs == 0L) {
            consec = 0;
            return;
        }
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("noslowdown");
        double maxBps = sec != null ? sec.getDouble("max_horizontal_bps", 4.0) : 4.0;
        int consecMid  = sec != null ? sec.getInt("consec_mid", 3) : 3;
        int consecHigh = sec != null ? sec.getInt("consec_high", 6) : 6;

        long dt = now - lastCheckMs;
        if (dt < 30L || dt > 500L) {
            lastCheckMs = now;
            return;
        }
        double dx = nx - s.lastX;
        double dz = nz - s.lastZ;
        double dist = Math.sqrt(dx * dx + dz * dz);
        double bps = dist * 1000.0 / dt;
        if (bps > maxBps) {
            consec++;
            if (consec >= consecHigh) {
                sink.flag(new Violation(player, "noslowdown_packet",
                    ViolationLevel.HIGH,
                    String.format("usando item bps=%.2f (max=%.2f) x%d", bps, maxBps, consec)));
                consec = 0;
            } else if (consec >= consecMid) {
                sink.flag(new Violation(player, "noslowdown_packet",
                    ViolationLevel.MID,
                    String.format("usando item bps=%.2f", bps)));
            }
        } else {
            consec = 0;
        }
        lastCheckMs = now;
    }
}
