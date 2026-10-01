package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import org.bukkit.Location;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.scheduler.BukkitTask;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * BowAimbot: mientras carga el arco, el aimbot sigue al objetivo tick a tick casi sin error
 * (el giro del jugador copia el giro angular del objetivo, con o sin prediccion constante).
 * Un humano corrige a saltos (residuo de 1-3 grados por tick). Se muestrea en el hilo
 * principal cada tick mientras dura la carga. Todo el estado vive en el hilo principal.
 */
public final class BowAimbotCheck {

    private static final int MAX_TICKS = 100;

    private final ArgusPlugin plugin;
    private final Map<UUID, Session> sessions = new HashMap<>();

    public BowAimbotCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    private static final class Track {
        double lastYawTo = Double.NaN;
        double sumResidual, sumTarget;
        int n;
    }

    private static final class Session {
        BukkitTask task;
        float lastYaw = Float.NaN;
        int ticks;
        final Map<UUID, Track> tracks = new HashMap<>();
    }

    public void startDraw(Player p) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("bow_aimbot")) return;
        stop(p.getUniqueId());
        Session s = new Session();
        s.task = plugin.getServer().getScheduler().runTaskTimer(plugin, () -> sample(p, s), 1L, 1L);
        sessions.put(p.getUniqueId(), s);
    }

    public void stop(UUID id) {
        Session s = sessions.remove(id);
        if (s != null && s.task != null) s.task.cancel();
    }

    private void sample(Player p, Session s) {
        if (!p.isOnline() || ++s.ticks > MAX_TICKS) {
            stop(p.getUniqueId());
            return;
        }
        Location eye = p.getEyeLocation();
        float yaw = eye.getYaw();
        for (Entity e : p.getNearbyEntities(50, 20, 50)) {
            if (!(e instanceof LivingEntity le)) continue;
            Location te = le.getEyeLocation();
            double yawTo = Math.toDegrees(Math.atan2(-(te.getX() - eye.getX()), te.getZ() - eye.getZ()));
            Track t = s.tracks.computeIfAbsent(e.getUniqueId(), k -> new Track());
            if (!Double.isNaN(t.lastYawTo) && !Float.isNaN(s.lastYaw)) {
                double dPlayer = wrap(yaw - s.lastYaw);
                double dTarget = wrap(yawTo - t.lastYawTo);
                t.sumResidual += Math.abs(dPlayer - dTarget);
                t.sumTarget += Math.abs(dTarget);
                t.n++;
            }
            t.lastYawTo = yawTo;
        }
        s.lastYaw = yaw;
    }

    public void onShoot(Player p, ViolationSink sink) {
        Session s = sessions.get(p.getUniqueId());
        stop(p.getUniqueId());
        if (s == null) return;
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("bow_aimbot");
        int minSamples = sec != null ? sec.getInt("min_samples", 8) : 8;
        double minTargetMotion = sec != null ? sec.getDouble("min_target_deg_per_tick", 0.5) : 0.5;
        double maxResidual = sec != null ? sec.getDouble("max_residual_deg", 0.25) : 0.25;

        double best = Double.MAX_VALUE, bestMotion = 0;
        for (Track t : s.tracks.values()) {
            if (t.n < minSamples || t.sumTarget / t.n < minTargetMotion) continue;
            double res = t.sumResidual / t.n;
            if (res < best) {
                best = res;
                bestMotion = t.sumTarget / t.n;
            }
        }
        if (best >= maxResidual) return;
        sink.flag(new Violation(p, "bow_aimbot_packet",
            best < maxResidual * 0.4 ? ViolationLevel.HIGH : ViolationLevel.MID,
            String.format("sigue al objetivo cargando el arco: error %.2f°/tick con objetivo moviendose %.1f°/tick",
                best, bestMotion)));
    }

    static double wrap(double d) {
        d %= 360;
        if (d > 180) d -= 360;
        if (d < -180) d += 360;
        return d;
    }
}
