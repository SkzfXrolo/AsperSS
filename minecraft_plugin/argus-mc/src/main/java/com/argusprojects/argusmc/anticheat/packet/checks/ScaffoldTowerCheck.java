package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class ScaffoldTowerCheck {

    private final ArgusPlugin plugin;

    public ScaffoldTowerCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBlockPlacement(Player player, PacketDataStore.State s,
                                     int placedX, int placedY, int placedZ,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("scaffold_tower")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("scaffold_tower");
        long maxInterval = sec != null ? sec.getLong("max_interval_ms", 300L) : 300L;
        int  consecMid   = sec != null ? sec.getInt("consec_mid", 3) : 3;
        int  consecHigh  = sec != null ? sec.getInt("consec_high", 5) : 5;

        // Se mide el tiempo ENTRE NIVELES: clickear varias veces el mismo bloque (jitter) no cuenta.
        // Pilarear legit sube un bloque por salto (~450ms); un tower hack, cada 100-250ms.
        if (placedY == s.lastScaffoldPlaceY && placedX == s.lastTowerX && placedZ == s.lastTowerZ) return;
        boolean sameCol = placedX == s.lastTowerX && placedZ == s.lastTowerZ;
        boolean yPlus1  = placedY == s.lastScaffoldPlaceY + 1;
        long dt = now - s.lastScaffoldPlaceMs;
        if (sameCol && yPlus1 && dt <= maxInterval) {
            s.scaffoldTowerConsec++;
            if (s.scaffoldTowerConsec >= consecHigh) {
                sink.flag(new Violation(player, "scaffold_tower_packet",
                    ViolationLevel.HIGH,
                    "torre a " + dt + "ms por bloque x" + s.scaffoldTowerConsec));
                s.scaffoldTowerConsec = 0;
            } else if (s.scaffoldTowerConsec >= consecMid) {
                sink.flag(new Violation(player, "scaffold_tower_packet",
                    ViolationLevel.MID,
                    "torre a " + dt + "ms por bloque x" + s.scaffoldTowerConsec));
            }
        } else {
            s.scaffoldTowerConsec = 0;
        }
        s.lastTowerX = placedX;
        s.lastTowerZ = placedZ;
        s.lastScaffoldPlaceMs = now;
        s.lastScaffoldPlaceY  = placedY;
    }
}
