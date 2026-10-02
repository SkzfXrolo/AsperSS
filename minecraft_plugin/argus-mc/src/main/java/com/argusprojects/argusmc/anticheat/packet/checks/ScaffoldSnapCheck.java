package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.util.NumberConversions;

/**
 * Scaffold con rotaciones: gira de golpe (>90 grados en un tick) para mirar el bloque, lo pone
 * bajo los pies y vuelve. Un humano no hace flicks de 90+ pegados a cada bloque que pone.
 * El orden rotacion/colocacion varia por cliente, asi que se acepta el giro antes o despues.
 */
public final class ScaffoldSnapCheck {

    private final ArgusPlugin plugin;

    public ScaffoldSnapCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s, float oldYaw, float oldPitch,
                               float yaw, float pitch, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("scaffold_snap")) return;
        if (Math.hypot(yawDelta(oldYaw, yaw), pitch - oldPitch) < minSnap()) return;
        s.scaffoldSnapMs = now;
        if (now - s.scaffoldBelowPlaceMs <= pairWindow()) hit(player, s, now, sink);
    }

    public void handlePlacement(Player player, PacketDataStore.State s, int clickedY, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("scaffold_snap")) return;
        // Puente: se clickea el bloque de abajo de los pies (o mas abajo).
        if (clickedY > NumberConversions.floor(s.lastY) - 1) return;
        s.scaffoldBelowPlaceMs = now;
        if (now - s.scaffoldSnapMs <= pairWindow()) hit(player, s, now, sink);
    }

    static double yawDelta(float a, float b) {
        return Math.abs(((b - a) % 360 + 540) % 360 - 180);
    }

    private void hit(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (now - s.scaffoldSnapLastHitMs <= pairWindow()) return; // un mismo par no cuenta dos veces
        s.scaffoldSnapLastHitMs = now;
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("scaffold_snap");
        long window = sec != null ? sec.getLong("window_ms", 10000L) : 10000L;
        int mid  = sec != null ? sec.getInt("hits_mid", 3) : 3;
        int high = sec != null ? sec.getInt("hits_high", 6) : 6;
        if (now - s.scaffoldSnapWindowStartMs > window) {
            s.scaffoldSnapWindowStartMs = now;
            s.scaffoldSnapHits = 0;
        }
        s.scaffoldSnapHits++;
        if (s.scaffoldSnapHits >= mid) {
            ViolationLevel lvl = s.scaffoldSnapHits >= high ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "scaffold_snap_packet", lvl,
                String.format("giro >%.0f° pegado a colocar bajo los pies x%d", minSnap(), s.scaffoldSnapHits)));
            if (lvl == ViolationLevel.HIGH) s.scaffoldSnapHits = 0;
        }
    }

    private double minSnap() {
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("scaffold_snap");
        return sec != null ? sec.getDouble("min_snap_deg", 90.0) : 90.0;
    }

    private long pairWindow() {
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("scaffold_snap");
        return sec != null ? sec.getLong("pair_window_ms", 250L) : 250L;
    }
}
