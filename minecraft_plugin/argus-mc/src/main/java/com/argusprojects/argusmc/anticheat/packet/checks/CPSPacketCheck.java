package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.entity.Player;

/**
 * Pack 47 — CPS verdadero a nivel packet.
 *
 * <p>El check de Bukkit-based usa {@code PlayerInteractEvent} que solo dispara
 * ~10 veces por segundo aunque clickees mas (clamping del server). A nivel
 * InteractEntity packet vemos el CPS REAL del cliente.
 *
 * <p>Umbrales (sliding window 1 segundo):
 * <ul>
 *   <li>&gt; 22 CPS: posible autoclicker (LOW)</li>
 *   <li>&gt; 30 CPS: autoclicker o butterfly extremo (MID)</li>
 *   <li>&gt; 45 CPS: AAA-autoclicker (HIGH)</li>
 * </ul>
 *
 * <p>Player drag-clicking puede llegar a 25-32 CPS legitimamente en burst
 * cortos, asi que mantenemos LOW/MID para esos rangos. Solo &gt;45 sostenido
 * disparara HIGH.
 */
public final class CPSPacketCheck {

    private final ArgusPlugin plugin;

    public CPSPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("cps_packet")) return;
        int cps = s.recentAttacksWithin(1_000L, now);
        if (cps >= 45) {
            sink.flag(new Violation(player, "cps_packet",
                ViolationLevel.HIGH,
                String.format("cps=%d (>45)", cps)));
        } else if (cps >= 30) {
            sink.flag(new Violation(player, "cps_packet",
                ViolationLevel.MID,
                String.format("cps=%d (>30)", cps)));
        } else if (cps >= 22) {
            sink.flag(new Violation(player, "cps_packet",
                ViolationLevel.LOW,
                String.format("cps=%d (>22)", cps)));
        }
    }
}
