package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * AutoSoup / AutoPot de hotbar: cambia al slot de la sopa, la usa y vuelve, todo en el mismo tick.
 * Un jugador de soup PvP rapido tarda ~100-200ms entre tecla, click y volver; el macro lo hace en <60ms.
 */
public final class AutoSoupCheck {

    private static final long FAST_MS = 60L;

    private final ArgusPlugin plugin;

    public AutoSoupCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleSlotChange(Player player, PacketDataStore.State s, int slot, long now, ViolationSink sink) {
        boolean usedJustNow = s.soupUseMs > 0 && now - s.soupUseMs < FAST_MS;
        s.lastSlotChangeMs = now;
        s.soupUseMs = 0;
        if (!usedJustNow || !plugin.getAnticheatConfig().isCheckEnabled("autosoup")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("autosoup");
        int mid  = sec != null ? sec.getInt("hits_mid", 3) : 3;
        int high = sec != null ? sec.getInt("hits_high", 6) : 6;
        if (now - s.soupWindowStartMs > 10_000L) {
            s.soupWindowStartMs = now;
            s.soupHits = 0;
        }
        s.soupHits++;
        if (s.soupHits >= mid) {
            ViolationLevel lvl = s.soupHits >= high ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "autosoup_packet", lvl,
                String.format("cambio de slot + usar + volver en <%dms x%d", FAST_MS, s.soupHits)));
            if (lvl == ViolationLevel.HIGH) s.soupHits = 0;
        }
    }

    public void handleUseItem(Player player, PacketDataStore.State s, long now) {
        if (now - s.lastSlotChangeMs >= FAST_MS) return;
        ItemStack held;
        try {
            // El cambio de slot llega por netty antes de que el server lo aplique: usar el slot del paquete.
            held = s.selectedSlot >= 0 ? player.getInventory().getItem(s.selectedSlot)
                                       : player.getInventory().getItemInMainHand();
            if (held == null) return;
        } catch (Throwable t) {
            return;
        }
        Material m = held.getType();
        if (m == Material.MUSHROOM_STEW || m == Material.SPLASH_POTION || m == Material.SUSPICIOUS_STEW) s.soupUseMs = now;
    }
}
