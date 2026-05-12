package com.argusprojects.argusmc.gui;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.SkullMeta;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Pack 48 round 3 — Lista de players bajo "watch mode".
 *
 * <p>Cada player con {@code state.watchedBy != null} aparece como una
 * player-head; el lore muestra el admin que los está observando. Click
 * izquierdo abre el {@link ViolationViewerGUI} para ese player.
 */
public final class WatchedPlayersGUI implements InventoryHolder {

    private final Inventory inv;

    public static void open(ArgusPlugin plugin, Player viewer) {
        WatchedPlayersGUI gui = new WatchedPlayersGUI(plugin);
        viewer.openInventory(gui.inv);
    }

    private WatchedPlayersGUI(ArgusPlugin plugin) {
        this.inv = Bukkit.createInventory(this, 54,
            ChatColor.AQUA + "Argus » Watched");

        var bs = plugin.getPacketEventsBootstrap();
        if (bs == null || bs.getDataStore() == null) return;

        int slot = 0;
        for (UUID uuid : bs.getDataStore().keys()) {
            if (slot >= 54) break;
            var s = bs.getDataStore().peek(uuid);
            if (s == null || s.watchedBy == null) continue;
            OfflinePlayer op = Bukkit.getOfflinePlayer(uuid);
            ItemStack head = new ItemStack(Material.PLAYER_HEAD);
            SkullMeta sm = (SkullMeta) head.getItemMeta();
            if (sm != null) {
                try { sm.setOwningPlayer(op); } catch (Throwable ignored) {}
                sm.setDisplayName(ChatColor.WHITE + (op.getName() == null ? uuid.toString() : op.getName()));
                List<String> lore = new ArrayList<>();
                OfflinePlayer admin = Bukkit.getOfflinePlayer(s.watchedBy);
                lore.add(ChatColor.GRAY + "Observado por: " + ChatColor.WHITE
                    + (admin.getName() == null ? s.watchedBy.toString() : admin.getName()));
                lore.add(ChatColor.GRAY + "Trust score: " + ChatColor.WHITE
                    + String.format("%.1f", s.trustScore));
                lore.add("");
                lore.add(ChatColor.YELLOW + "LEFT click: ver violations");
                lore.add(ChatColor.RED    + "RIGHT click: stop watching");
                sm.setLore(lore);
                head.setItemMeta(sm);
            }
            inv.setItem(slot++, head);
        }
        if (slot == 0) {
            ItemMeta meta;
            ItemStack empty = new ItemStack(Material.PAPER);
            meta = empty.getItemMeta();
            meta.setDisplayName(ChatColor.GRAY + "(no hay jugadores observados)");
            empty.setItemMeta(meta);
            inv.setItem(22, empty);
        }
    }

    @Override
    public Inventory getInventory() { return inv; }
}
