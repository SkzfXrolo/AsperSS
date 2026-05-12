package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — KillauraAimCheck (aim "perfecto" antes de hit).
 *
 * <p>Los killauras snapshot la rotacion del cliente al target en el mismo tick
 * del attack, dejando rotation deltas demasiado limpios (&lt; 0.1 grados). Un
 * humano tiene micro-jitter constante incluso al apuntar perfectamente.
 *
 * <p>Heuristica: si en los ultimos N packets de rotation antes del attack
 * el delta acumulado fue casi cero (&lt; threshold) pero entre el packet
 * anterior y el del attack hay un delta MAYOR (snap), eso indica aim asistido.
 *
 * <p>Tambien medimos "rotation stability": si entre los ultimos 3 packets de
 * rotation pre-attack el desvio estandar es 0 (exactamente igual), eso es
 * un bot que no esta moviendo el mouse en absoluto.
 */
public final class KillauraAimCheck {

    private final ArgusPlugin plugin;

    public KillauraAimCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target, PacketDataStore.State s,
                             long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("killaura_aim")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("killaura_aim");
        double maxMicroJitter = sec != null ? sec.getDouble("max_micro_jitter_deg", 0.05) : 0.05;
        long windowMs         = sec != null ? sec.getLong("window_ms", 250L) : 250L;
        int minRotationSamples= sec != null ? sec.getInt("min_samples", 3) : 3;

        // Stability check: si las ultimas N rotaciones son IDENTICAS hasta el
        // ultimo bit float, no es un humano apuntando con el mouse.
        int samples;
        double yawSpread = 0.0;
        double pitchSpread = 0.0;
        synchronized (s) {
            samples = s.recentRotations.size();
            if (samples >= minRotationSamples) {
                float minY = Float.POSITIVE_INFINITY, maxY = Float.NEGATIVE_INFINITY;
                float minP = Float.POSITIVE_INFINITY, maxP = Float.NEGATIVE_INFINITY;
                long  cutoff = now - windowMs;
                int   counted = 0;
                for (PacketDataStore.RotationSample r : s.recentRotations) {
                    if (r.tsMs < cutoff) continue;
                    counted++;
                    if (r.yaw   < minY) minY = r.yaw;
                    if (r.yaw   > maxY) maxY = r.yaw;
                    if (r.pitch < minP) minP = r.pitch;
                    if (r.pitch > maxP) maxP = r.pitch;
                }
                samples = counted;
                yawSpread = maxY - minY;
                pitchSpread = maxP - minP;
            }
        }

        if (samples < minRotationSamples) return;
        // Aim "stuck" perfecto: spread total < threshold combinado.
        double combinedSpread = Math.sqrt(yawSpread * yawSpread + pitchSpread * pitchSpread);
        if (combinedSpread < maxMicroJitter) {
            sink.flag(new Violation(player, "killaura_aim_packet",
                ViolationLevel.HIGH,
                String.format("rotation frozen %d samples spread=%.4f° (<%.3f°)",
                    samples, combinedSpread, maxMicroJitter)));
        }
    }
}
