package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — AntiKnockbackCheck.
 *
 * <p>Cuando el server le asigna una velocidad de knockback al cliente
 * (al recibir daño), el cliente vanilla debe mostrarla en su movimiento
 * en los próximos packets. Si el delta horizontal observado es mucho
 * menor que el KB asignado, es anti-knockback.
 *
 * <p>El bridge setea {@link PacketDataStore.State#lastKnockbackExpectedMs}
 * y {@code lastKnockbackExpectedMag} al observar
 * {@code EntityDamageEvent}. Este check compara el movimiento en los N
 * packets siguientes vs ese KB esperado.
 */
public final class AntiKnockbackCheck {

    private final ArgusPlugin plugin;

    public AntiKnockbackCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double nz, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("antikb")) return;
        if (s.lastKnockbackExpectedMs == 0L) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("antikb");
        long windowMs    = sec != null ? sec.getLong("window_ms", 500L) : 500L;
        double ratioMax  = sec != null ? sec.getDouble("max_ratio", 0.3) : 0.3;
        int consecMid    = sec != null ? sec.getInt("consec_mid", 2) : 2;
        int consecHigh   = sec != null ? sec.getInt("consec_high", 4) : 4;

        long since = now - s.lastKnockbackExpectedMs;
        if (since > windowMs) {
            // ventana expirada — reset.
            s.lastKnockbackExpectedMs = 0L;
            s.antiKbConsec = 0;
            return;
        }

        double dx = nx - s.lastX;
        double dz = nz - s.lastZ;
        double observed = Math.sqrt(dx * dx + dz * dz);
        double expected = s.lastKnockbackExpectedMag;
        if (expected <= 0.01) return;

        double ratio = observed / expected;
        if (ratio < ratioMax) {
            s.antiKbConsec++;
            if (s.antiKbConsec >= consecHigh) {
                sink.flag(new Violation(player, "antikb_packet",
                    ViolationLevel.HIGH,
                    String.format("KB obs=%.3f exp=%.3f ratio=%.2f", observed, expected, ratio)));
                s.antiKbConsec = 0;
                s.lastKnockbackExpectedMs = 0L;
            } else if (s.antiKbConsec >= consecMid) {
                sink.flag(new Violation(player, "antikb_packet",
                    ViolationLevel.MID,
                    String.format("KB obs=%.3f exp=%.3f", observed, expected)));
            }
        } else {
            s.antiKbConsec = 0;
            s.lastKnockbackExpectedMs = 0L;
        }
    }
}
