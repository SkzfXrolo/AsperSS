package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 47 — InvMove (inventory + movement simultaneo).
 *
 * <p>Cliente vanilla NO envia movement packets mientras tiene el inventario
 * abierto (la GUI bloquea el input WASD). Algunos hacks ("InvMove") permiten
 * mover/saltar mientras manejas el inventario, lo cual es ventaja PvP.
 *
 * <p>Heuristica: si el cliente abrio inventario hace &gt;=300ms y desde entonces
 * ha enviado packets de movimiento (lastMoveMs &gt;= inventoryOpenSinceMs + 300),
 * o hace clicks en window mientras camina, es invmove.
 *
 * <p>NOTA: el horse/villager UI permite movimiento (no flagea). Solo chequeamos
 * cuando se abre un inv "fijo" — esto lo regula el bridge bukkit que marca
 * inventoryOpen=true SOLO en InventoryOpenEvent legitimo (no en horse).
 */
public final class InvMovePacketCheck {

    private final ArgusPlugin plugin;

    public InvMovePacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleClickWindow(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("inv_move_packet")) return;
        if (!s.inventoryOpen) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("inv_move_packet");
        long graceMs       = sec != null ? sec.getLong("grace_ms",         300L) : 300L;
        long staleMoveMs   = sec != null ? sec.getLong("stale_move_ms",  1_000L) : 1_000L;

        if (now - s.inventoryOpenSinceMs < graceMs) return;

        if (s.lastMoveMs > s.inventoryOpenSinceMs + graceMs
            && now - s.lastMoveMs < staleMoveMs) {
            sink.flag(new Violation(player, "inv_move_packet",
                ViolationLevel.MID,
                String.format("clickWindow during movement (lastMove %dms ago, invOpen %dms)",
                    now - s.lastMoveMs, now - s.inventoryOpenSinceMs)));
        }
    }
}
