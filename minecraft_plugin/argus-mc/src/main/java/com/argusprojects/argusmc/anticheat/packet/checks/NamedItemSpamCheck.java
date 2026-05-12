package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

/**
 * Pack 48 round2 — NamedItemSpamCheck.
 *
 * <p>Detecta el "AutoNamer" / farm-bot que cambia el nombre del item en
 * mano con altisima frecuencia para evadir filtros o farmear logros.
 *
 * <p>Heuristica: si el nombre del item en main hand cambia &gt; N veces
 * en {@code window_ms}, flag.
 */
public final class NamedItemSpamCheck {

    private final ArgusPlugin plugin;

    public NamedItemSpamCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleHeldItemChange(Player player, PacketDataStore.State s, long now,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("named_item_spam")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("named_item_spam");
        long windowMs    = sec != null ? sec.getLong("window_ms", 1500L) : 1500L;
        int    minChanges= sec != null ? sec.getInt("min_changes", 6) : 6;

        ItemStack inHand;
        try {
            inHand = player.getInventory().getItemInMainHand();
        } catch (Throwable t) {
            return;
        }
        String currentName = null;
        if (inHand != null && inHand.hasItemMeta()) {
            ItemMeta meta = inHand.getItemMeta();
            if (meta != null && meta.hasDisplayName()) {
                currentName = meta.getDisplayName();
            }
        }
        if (currentName == null) return; // no es item renombrado

        if (s.lastMainHandItemName != null && !currentName.equals(s.lastMainHandItemName)) {
            // Conteo de cambios: aprovechamos lastMainHandItemNameMs como inicio de ventana.
            long sinceWindowStart = now - s.lastMainHandItemNameMs;
            if (sinceWindowStart > windowMs) {
                s.lastMainHandItemNameMs = now;
                s.namedChangesInWindow = 1;
            } else {
                s.namedChangesInWindow++;
                if (s.namedChangesInWindow >= minChanges) {
                    sink.flag(new Violation(player, "named_item_spam_packet",
                        ViolationLevel.MID,
                        String.format("renames=%d en %dms", s.namedChangesInWindow, sinceWindowStart)));
                    s.namedChangesInWindow = 0;
                    s.lastMainHandItemNameMs = now;
                }
            }
        }
        s.lastMainHandItemName = currentName;
        if (s.lastMainHandItemNameMs == 0) s.lastMainHandItemNameMs = now;
    }
}
