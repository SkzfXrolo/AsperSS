package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * AimAssist / Aimbot suave: el mouse mueve la camara en pasos enteros de F = (sens*0.6+0.2)^3 * 1.2
 * grados (min 0.0096 con sensibilidad 0). Todo giro hecho con el mouse es multiplo de F, asi que el MCD
 * de dos giros de pitch seguidos es >= F. Un aim assist suma angulos calculados (no multiplos) y el MCD
 * se desarma. Solo se mira en combate y con muchas muestras.
 */
public final class AimGcdCheck {

    static final double MIN_MOUSE_STEP = 0.0096;
    private static final double TOLERANCE = 1e-4;

    private final ArgusPlugin plugin;

    public AimGcdCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s, float oldPitch, float pitch, long now,
                               ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("aim_gcd")) return;
        if (Math.abs(pitch) > 85 || Math.abs(oldPitch) > 85) return; // clamp de pitch rompe los multiplos
        double d = Math.abs(pitch - oldPitch);
        if (d < 0.02 || d > 20) return;
        double prev = s.gcdLastDelta;
        s.gcdLastDelta = d;
        if (prev <= 0) return;
        double g = gcd(Math.max(d, prev), Math.min(d, prev));

        // Aprende el paso de mouse del jugador con TODOS sus giros (no solo en pelea).
        if (g >= MIN_MOUSE_STEP * 0.9 && g <= 2.0) learn(s, g);
        if (now - s.lastAttackMs > 1_500L) {                     // se evalua solo en pelea, cada pelea por separado
            s.gcdSamples = 0;
            s.gcdNonMouse = 0;
            return;
        }

        s.gcdSamples++;
        if (g < MIN_MOUSE_STEP * 0.9 || offGrid(d, s.gcdSensEstimate)) s.gcdNonMouse++;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("aim_gcd");
        int samples = sec != null ? sec.getInt("samples", 40) : 40;
        double ratioMid = sec != null ? sec.getDouble("ratio_mid", 0.6) : 0.6;
        if (s.gcdSamples < samples) return;
        double ratio = s.gcdNonMouse / (double) s.gcdSamples;
        s.gcdSamples = 0;
        s.gcdNonMouse = 0;
        if (ratio < ratioMid) return;
        sink.flag(new Violation(player, "aim_gcd_packet",
            ratio >= 0.85 ? ViolationLevel.HIGH : ViolationLevel.MID,
            String.format("%.0f%% de los giros en pelea no son pasos de mouse (aim assist)", ratio * 100)));
    }

    private static void learn(PacketDataStore.State s, double g) {
        synchronized (s.gcdCandidates) {
            s.gcdCandidates.addLast(g);
            while (s.gcdCandidates.size() > 60) s.gcdCandidates.pollFirst();
            if (++s.gcdLearnCount % 10 == 0) s.gcdSensEstimate = estimate(s.gcdCandidates.stream().mapToDouble(Double::doubleValue).toArray());
        }
    }

    /** Paso de mouse = el MCD mas chico que se repite (>=4 veces, +-2%). 0 si todavia no hay patron. */
    static double estimate(double[] candidates) {
        double[] c = candidates.clone();
        java.util.Arrays.sort(c);
        for (double base : c) {
            int n = 0;
            for (double x : c) if (Math.abs(x - base) <= base * 0.02) n++;
            if (n >= 4) return base;
        }
        return 0;
    }

    /** El giro no es un multiplo entero del paso de mouse aprendido. */
    static boolean offGrid(double d, double step) {
        if (step <= 0) return false;
        double r = d / step;
        return r < 400 && Math.abs(r - Math.rint(r)) > 0.15;
    }

    /** MCD de reales con tolerancia (los floats acumulan error de redondeo). */
    static double gcd(double a, double b) {
        while (b > TOLERANCE) {
            double r = a - Math.floor(a / b) * b;
            a = b;
            b = r;
        }
        return a;
    }
}
