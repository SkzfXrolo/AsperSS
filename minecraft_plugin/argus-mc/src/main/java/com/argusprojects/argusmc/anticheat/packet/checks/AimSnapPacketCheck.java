package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.entity.Player;

/**
 * Pack 47 — AimSnap (aim-assist / kill-aura aiming).
 *
 * <p>Mide el delta yaw entre packets de rotation consecutivos. Un humano
 * gira el mouse con curva (~10-25° por packet en giros bruscos). Killaura
 * y aimbot snap-rotan, produciendo deltas tipo &gt;60° en un solo tick. La
 * heuristica:
 *
 * <ul>
 *   <li>Delta &gt; 80° en un packet (50ms) → snap probable (MID)</li>
 *   <li>Delta &gt; 80° seguido inmediatamente por un attack (&lt; 100ms despues)
 *       → snap + hit, casi seguro killaura (HIGH)</li>
 * </ul>
 *
 * <p>Para evitar FPs por usuarios que giran rapido la camara, exigimos que
 * dentro de 200ms post-snap haya un attack a un target o el snap se ignora
 * (se computa pero no flagea).
 */
public final class AimSnapPacketCheck {

    private static final double SNAP_DELTA_THRESHOLD = 80.0;
    private static final long   SNAP_TO_ATTACK_WINDOW_MS = 200L;

    private final ArgusPlugin plugin;

    public AimSnapPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s, float yaw, float pitch, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("aim_snap_packet")) return;

        // Sin baseline aun.
        if (s.lastYaw == 0 && s.lastPitch == 0) return;

        float dyaw = wrap(yaw - s.lastYaw);
        float dpitch = pitch - s.lastPitch;
        double delta = Math.sqrt(dyaw * dyaw + dpitch * dpitch);

        if (delta >= SNAP_DELTA_THRESHOLD) {
            long now = System.currentTimeMillis();
            long sinceAttack = now - s.lastAttackMs;
            if (s.lastAttackMs > 0 && sinceAttack <= SNAP_TO_ATTACK_WINDOW_MS) {
                // Snap + attack reciente = killaura aiming
                sink.flag(new Violation(player, "aim_snap_packet",
                    ViolationLevel.HIGH,
                    String.format("delta=%.1f° dyaw=%.1f° dpitch=%.1f° sinceAttack=%dms", delta, dyaw, dpitch, sinceAttack)));
            } else if (delta >= 130.0) {
                // Snap muy extremo aislado (incluso sin attack inmediato)
                sink.flag(new Violation(player, "aim_snap_packet",
                    ViolationLevel.MID,
                    String.format("delta=%.1f° (no recent attack)", delta)));
            }
        }
    }

    private static float wrap(float dyaw) {
        while (dyaw <= -180.0f) dyaw += 360.0f;
        while (dyaw >   180.0f) dyaw -= 360.0f;
        return dyaw;
    }
}
