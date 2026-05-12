package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — BowAimCheck.
 *
 * <p>Detecta cuando un jugador apunta y dispara el arco con un "snap"
 * inmediatamente antes del release: la rotacion cambia bruscamente
 * (snap >X grados) en los ultimos ~100ms antes de soltar el arco,
 * consistente con aim-assist clasico.
 *
 * <p>Se invoca desde {@link org.bukkit.event.entity.EntityShootBowEvent}
 * en el bridge Bukkit. Mira el buffer de rotaciones en
 * {@link PacketDataStore.State#recentRotations}.
 */
public final class BowAimCheck {

    private final ArgusPlugin plugin;

    public BowAimCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleShoot(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("bow_aim")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("bow_aim");
        long windowMs   = sec != null ? sec.getLong("window_ms", 150L) : 150L;
        double snapDeg  = sec != null ? sec.getDouble("snap_deg", 25.0) : 25.0;

        long cutoff = now - windowMs;
        PacketDataStore.RotationSample first = null, last = null;
        synchronized (s) {
            for (PacketDataStore.RotationSample r : s.recentRotations) {
                if (r.tsMs < cutoff) continue;
                if (first == null) first = r;
                last = r;
            }
        }
        if (first == null || last == null || first == last) return;
        float dy = last.yaw - first.yaw;
        // normaliza a [-180, 180]
        while (dy > 180) dy -= 360;
        while (dy < -180) dy += 360;
        float dp = last.pitch - first.pitch;
        double delta = Math.sqrt(dy * dy + dp * dp);
        if (delta >= snapDeg) {
            sink.flag(new Violation(player, "bow_aim_packet",
                ViolationLevel.HIGH,
                String.format("rotation snap %.1f° en <=%dms antes de shoot", delta, windowMs)));
        }
    }
}
