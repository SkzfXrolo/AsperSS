package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — ScaffoldTowerCheck.
 *
 * <p>Detecta torres verticales perfectas: bloques colocados uno arriba
 * del otro en pocos ms, con el jugador saltando exactamente sobre el
 * bloque recién colocado. Las "tower scaffold" cheats lo hacen en
 * ráfaga.
 *
 * <p>Pattern:
 * <ul>
 *   <li>Misma columna X/Z que el placement anterior.</li>
 *   <li>Y incremento = +1 exacto del previo.</li>
 *   <li>Intervalo &lt; {@code max_interval_ms} (default 250ms).</li>
 *   <li>Repeticiones &gt;= {@code consec_high} (default 5).</li>
 * </ul>
 */
public final class ScaffoldTowerCheck {

    private final ArgusPlugin plugin;
    private int lastX, lastZ;

    public ScaffoldTowerCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBlockPlacement(Player player, PacketDataStore.State s,
                                     int placedX, int placedY, int placedZ,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("scaffold_tower")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("scaffold_tower");
        long maxInterval = sec != null ? sec.getLong("max_interval_ms", 250L) : 250L;
        int  consecMid   = sec != null ? sec.getInt("consec_mid", 3) : 3;
        int  consecHigh  = sec != null ? sec.getInt("consec_high", 5) : 5;

        boolean sameCol = (placedX == lastX) && (placedZ == lastZ);
        boolean yPlus1  = (placedY == s.lastScaffoldPlaceY + 1);
        long dt = now - s.lastScaffoldPlaceMs;
        if (sameCol && yPlus1 && dt <= maxInterval) {
            s.scaffoldTowerConsec++;
            if (s.scaffoldTowerConsec >= consecHigh) {
                sink.flag(new Violation(player, "scaffold_tower_packet",
                    ViolationLevel.HIGH,
                    "tower vertical x" + s.scaffoldTowerConsec + " dt=" + dt + "ms"));
                s.scaffoldTowerConsec = 0;
            } else if (s.scaffoldTowerConsec >= consecMid) {
                sink.flag(new Violation(player, "scaffold_tower_packet",
                    ViolationLevel.MID,
                    "tower x" + s.scaffoldTowerConsec));
            }
        } else {
            s.scaffoldTowerConsec = 0;
        }
        lastX = placedX;
        lastZ = placedZ;
        s.lastScaffoldPlaceMs = now;
        s.lastScaffoldPlaceY  = placedY;
    }
}
