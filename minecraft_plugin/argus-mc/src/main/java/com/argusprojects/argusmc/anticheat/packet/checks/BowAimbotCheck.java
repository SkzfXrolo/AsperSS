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
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * BowAimbot: mientras carga el arco, el aimbot mantiene la mira clavada sobre un objetivo que se
 * mueve. Cada tick se mide el error angular (yaw + pitch) entre la mira y el objetivo:
 *  - aimbot: el error se mantiene casi constante (aunque apunte adelantado por la prediccion),
 *    desvio < ~0.8 grados;
 *  - humano: corrige a saltos, desvio de 2-5 grados.
 * Se mide el error absoluto (no el giro tick a tick) porque con lag el server aplica las
 * rotaciones a saltos y eso inflaria cualquier medida de "giro por tick".
 * Solo cuenta si el objetivo se mueve en pantalla y es al que apunta (error medio chico).
 * Todo el estado vive en el hilo principal.
 */
public final class BowAimbotCheck {

    private static final int MAX_TICKS = 100;
    // ponytail: umbral calibrado con 1 jugador real (0.74 legit) y bots; recalibrar con debug:true si hay quejas.

    private final ArgusPlugin plugin;
    private final Map<UUID, Session> sessions = new HashMap<>();
    private final Map<UUID, long[]> suspiciousShots = new HashMap<>();

    public BowAimbotCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /** Serie de un objetivo durante la carga. */
    static final class Track {
        /** Los primeros ticks de cada tiro son el "enganche" a el objetivo (humano o aimbot): no cuentan. */
        static final int ACQUIRE_TICKS = 6;
        double sumErr, sumErrSq, sumMotion;
        int n, seen;
        double lastYawTo = Double.NaN, lastPitchTo = Double.NaN;

        void add(double err, double yawTo, double pitchTo) {
            if (++seen <= ACQUIRE_TICKS) return;
            if (!Double.isNaN(lastYawTo)) sumMotion += Math.hypot(wrap(yawTo - lastYawTo), pitchTo - lastPitchTo);
            lastYawTo = yawTo;
            lastPitchTo = pitchTo;
            sumErr += err;
            sumErrSq += err * err;
            n++;
        }

        double meanErr() { return n == 0 ? Double.MAX_VALUE : sumErr / n; }
        double stdErr() { double m = meanErr(); return Math.sqrt(Math.max(0, sumErrSq / n - m * m)); }
        double motion() { return n < 2 ? 0 : sumMotion / (n - 1); }
    }

    private static final class Session {
        BukkitTask task;
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
        Vector look = eye.getDirection();
        for (Entity e : p.getNearbyEntities(60, 25, 60)) {
            if (!(e instanceof LivingEntity)) continue;
            BoundingBox bb = e.getBoundingBox();
            double dx = bb.getCenterX() - eye.getX(), dy = bb.getCenterY() - eye.getY(), dz = bb.getCenterZ() - eye.getZ();
            double dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
            if (dist < 4) continue;                       // de cerca no es tiro de arco
            Vector to = new Vector(dx / dist, dy / dist, dz / dist);
            double err = Math.toDegrees(Math.acos(Math.max(-1, Math.min(1, look.dot(to)))));
            if (err > 25) continue;                       // ni lo esta mirando
            double yawTo = Math.toDegrees(Math.atan2(-dx, dz));
            double pitchTo = -Math.toDegrees(Math.atan2(dy, Math.hypot(dx, dz)));
            s.tracks.computeIfAbsent(e.getUniqueId(), k -> new Track()).add(err, yawTo, pitchTo);
        }
    }

    public void onShoot(Player p, ViolationSink sink) {
        Session s = sessions.get(p.getUniqueId());
        stop(p.getUniqueId());
        if (s == null) return;
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("bow_aimbot");
        int minSamples = sec != null ? sec.getInt("min_samples", 10) : 10;
        double minMotion = sec != null ? sec.getDouble("min_target_deg_per_tick", 0.4) : 0.4;
        double maxStd = sec != null ? sec.getDouble("max_error_stddev_deg", 0.45) : 0.45;

        // Objetivo = al que apunta (menor error medio) entre los que estuvo mirando toda la carga.
        Track best = null;
        for (Track t : s.tracks.values()) {
            if (t.n < minSamples) continue;
            if (best == null || t.meanErr() < best.meanErr()) best = t;
        }
        if (sec != null && sec.getBoolean("debug", false)) {
            plugin.getLogger().info(best == null ? "[bow_aimbot] " + p.getName() + " sin objetivo (" + s.tracks.size() + " pistas)"
                : String.format("[bow_aimbot] %s n=%d errMedio=%.2f desvio=%.2f movimiento=%.2f", p.getName(), best.n, best.meanErr(), best.stdErr(), best.motion()));
        }
        if (best == null || best.meanErr() > 6.0 || best.motion() < minMotion) return;
        if (!isLockedOn(best, maxStd)) return;

        long now = System.currentTimeMillis();
        long[] shots = suspiciousShots.computeIfAbsent(p.getUniqueId(), k -> new long[]{0, 0});
        if (now - shots[1] > 60_000L) shots[0] = 0;
        shots[0]++;
        shots[1] = now;
        ViolationLevel lvl = shots[0] >= 3 || best.stdErr() < maxStd * 0.3 ? ViolationLevel.HIGH : ViolationLevel.MID;
        sink.flag(new Violation(p, "bow_aimbot_packet", lvl,
            String.format("mira clavada en el objetivo cargando el arco: desvio %.2f° (objetivo moviendose %.1f°/tick) x%d",
                best.stdErr(), best.motion(), shots[0])));
    }

    /**
     * El error de la mira contra un objetivo en movimiento casi no varia: eso no lo hace una mano.
     * Se mide relativo al movimiento: seguir algo rapido con desvio chico es lo imposible
     * Un humano bueno siguiendo algo lento llega a ~0.7 de desvio; un aimbot real queda < 0.3.
     */
    static boolean isLockedOn(Track t, double maxStd) {
        double std = t.stdErr(), motion = Math.max(0.05, t.motion());
        return std < maxStd && std / motion < 0.8;
    }

    static double wrap(double d) {
        d %= 360;
        if (d > 180) d -= 360;
        if (d < -180) d += 360;
        return d;
    }
}
