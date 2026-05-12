package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — InventoryTeleportCheck.
 *
 * <p>Variante de InvMove ya existente, pero invertida: el cheat "InventoryMove"
 * permite mover el inventario mientras te mueves. Aca detectamos el patron
 * de teleport: click rapido en inventory mientras la posicion cambia muy
 * bruscamente entre dos packets (un "blink").
 *
 * <p>Heuristica: si {@code lastClickWindowMs} y posicion cambia &gt; threshold
 * en &lt; 50ms entre los packets, flag.
 */
public final class InventoryTeleportCheck {

    private final ArgusPlugin plugin;

    public InventoryTeleportCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("inventory_teleport")) return;
        if (!s.inventoryOpen) return;
        if (s.lastClickWindowMs == 0) return;
        if (now - s.lastClickWindowMs > 500) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("inventory_teleport");
        double minBlink = sec != null ? sec.getDouble("min_blink_blocks", 2.0) : 2.0;
        long maxInterval= sec != null ? sec.getLong("max_packet_interval_ms", 80L) : 80L;

        long dtMs = now - s.lastMoveMs;
        if (dtMs > maxInterval) return;

        double dx = nx - s.lastX, dy = ny - s.lastY, dz = nz - s.lastZ;
        double dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        if (dist >= minBlink) {
            sink.flag(new Violation(player, "inventory_teleport_packet",
                ViolationLevel.HIGH,
                String.format("blink %.2fb en %dms con inv abierto", dist, dtMs)));
        }
    }
}
