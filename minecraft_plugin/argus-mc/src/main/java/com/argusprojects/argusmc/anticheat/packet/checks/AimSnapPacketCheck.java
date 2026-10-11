package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class AimSnapPacketCheck {

    private static final double DEFAULT_SNAP_DELTA = 80.0;
    private static final long   DEFAULT_SNAP_TO_ATTACK_MS = 200L;
    private static final double DEFAULT_EXTREME_SNAP = 130.0;

    private final ArgusPlugin plugin;

    public AimSnapPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleRotation(Player player, PacketDataStore.State s, float yaw, float pitch, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("aim_snap_packet")) return;
        if (s.lastYaw == 0 && s.lastPitch == 0) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("aim_snap_packet");
        double snapThreshold    = sec != null ? sec.getDouble("snap_delta_deg",  DEFAULT_SNAP_DELTA)        : DEFAULT_SNAP_DELTA;
        double extremeSnap      = sec != null ? sec.getDouble("extreme_delta_deg", DEFAULT_EXTREME_SNAP)    : DEFAULT_EXTREME_SNAP;
        long   attackWindowMs   = sec != null ? sec.getLong("snap_to_attack_ms",  DEFAULT_SNAP_TO_ATTACK_MS) : DEFAULT_SNAP_TO_ATTACK_MS;

        float dyaw = wrap(yaw - s.lastYaw);
        float dpitch = pitch - s.lastPitch;
        double delta = Math.sqrt(dyaw * dyaw + dpitch * dpitch);

        if (delta >= snapThreshold) {
            long now = System.currentTimeMillis();
            long sinceAttack = now - s.lastAttackMs;
            if (s.lastAttackMs > 0 && sinceAttack <= attackWindowMs) {
                sink.flag(new Violation(player, "aim_snap_packet",
                    ViolationLevel.HIGH,
                    String.format("delta=%.1f° dyaw=%.1f° dpitch=%.1f° sinceAttack=%dms", delta, dyaw, dpitch, sinceAttack)));
            // Girar rapido sin pegar es normal (darse vuelta en PvP 1.8): no se alerta.
            }
        }
    }

    private static float wrap(float dyaw) {
        while (dyaw <= -180.0f) dyaw += 360.0f;
        while (dyaw >   180.0f) dyaw -= 360.0f;
        return dyaw;
    }
}
