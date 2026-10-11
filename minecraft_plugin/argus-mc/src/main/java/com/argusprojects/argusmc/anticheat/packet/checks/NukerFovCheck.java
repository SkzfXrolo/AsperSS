package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Nuker: rompe los bloques de alrededor (atras, abajo, a los costados) sin mirarlos. Vanilla solo
 * puede picar el bloque que tiene en la mira. No mira velocidad: en prisiones se pica rapidisimo
 * legit con haste + eficiencia.
 */
public final class NukerFovCheck {

    private final ArgusPlugin plugin;

    public NukerFovCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleStartDigging(Player player, PacketDataStore.State s, int bx, int by, int bz, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("nuker_fov")) return;
        if (player.getGameMode() == GameMode.CREATIVE || player.getGameMode() == GameMode.SPECTATOR) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return;

        double angle = Math.min(offAngle(s.lastX, s.lastY + eye(player), s.lastZ, s.lastYaw, s.lastPitch, bx, by, bz),
                                offAngle(s.lastX, s.lastY + eye(player), s.lastZ, s.prevYaw, s.prevPitch, bx, by, bz));
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("nuker_fov");
        double maxAngle = sec != null ? sec.getDouble("max_angle_deg", 50.0) : 50.0;
        if (angle <= maxAngle) return;

        long window = sec != null ? sec.getLong("window_ms", 5_000L) : 5_000L;
        int mid  = sec != null ? sec.getInt("hits_mid", 4) : 4;
        int high = sec != null ? sec.getInt("hits_high", 8) : 8;
        if (now - s.nukerFovWindowStartMs > window) {
            s.nukerFovWindowStartMs = now;
            s.nukerFovHits = 0;
        }
        s.nukerFovHits++;
        if (s.nukerFovHits >= mid) {
            ViolationLevel lvl = s.nukerFovHits >= high ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "nuker_fov_packet", lvl,
                String.format("rompe bloques fuera de la mira (%.0f°) x%d", angle, s.nukerFovHits)));
            if (lvl == ViolationLevel.HIGH) s.nukerFovHits = 0;
        }
    }

    private static double eye(Player p) {
        return p.isSneaking() ? 1.27 : 1.62;
    }

    /** Angulo entre la mira y el bloque, descontando su tamano angular (se puede picar por un borde). */
    static double offAngle(double ex, double ey, double ez, float yawDeg, float pitchDeg, int bx, int by, int bz) {
        double tx = bx + 0.5 - ex, ty = by + 0.5 - ey, tz = bz + 0.5 - ez;
        double len = Math.sqrt(tx * tx + ty * ty + tz * tz);
        if (len < 1.0) return 0;                         // pegado a la cara: cualquier angulo es posible
        double yaw = Math.toRadians(yawDeg), pitch = Math.toRadians(pitchDeg);
        double lx = -Math.sin(yaw) * Math.cos(pitch), ly = -Math.sin(pitch), lz = Math.cos(yaw) * Math.cos(pitch);
        double dot = Math.max(-1.0, Math.min(1.0, (lx * tx + ly * ty + lz * tz) / len));
        double radius = Math.toDegrees(Math.atan(0.87 / len));
        return Math.max(0, Math.toDegrees(Math.acos(dot)) - radius);
    }
}
