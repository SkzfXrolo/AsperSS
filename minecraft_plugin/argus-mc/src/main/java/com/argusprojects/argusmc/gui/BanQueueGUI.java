package com.argusprojects.argusmc.gui;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.List;

/**
 * Pack 48 round 3 — GUI de "bans pendientes de aprobación".
 *
 * <p>El backend Argus puede mantener una cola de bans propuestos
 * (violations CRITICAL acumulados) que requieren approval manual del
 * staff antes de ejecutarse. Este GUI los lista; click izquierdo
 * aprueba, click derecho rechaza.
 *
 * <p>Por ahora muestra una vista placeholder con los recent CRITICAL
 * violations — la integración real con la API de bans-pendientes se
 * hace en {@code BanQueueClient} (next pack).
 */
public final class BanQueueGUI implements InventoryHolder {

    private final Inventory inv;

    public static void open(ArgusPlugin plugin, Player viewer) {
        BanQueueGUI gui = new BanQueueGUI(plugin);
        viewer.openInventory(gui.inv);
    }

    private BanQueueGUI(ArgusPlugin plugin) {
        this.inv = Bukkit.createInventory(this, 54,
            ChatColor.DARK_RED + "Argus » Ban Queue");

        var vm = plugin.getViolationManager();
        if (vm == null) return;
        var recent = vm.snapshotGlobalRecent(200);
        int slot = 0;
        for (int i = recent.size() - 1; i >= 0 && slot < 54; i--) {
            var v = recent.get(i);
            if (v.level != com.argusprojects.argusmc.anticheat.ViolationLevel.CRITICAL) continue;
            ItemStack it = new ItemStack(Material.RED_BANNER);
            ItemMeta meta = it.getItemMeta();
            meta.setDisplayName(ChatColor.RED + v.playerName + " " + ChatColor.WHITE + "[" + v.checkName + "]");
            List<String> lore = new ArrayList<>();
            lore.add(ChatColor.GRAY + "UUID: " + ChatColor.WHITE + v.playerUuid);
            lore.add(ChatColor.GRAY + "Time: " + ChatColor.WHITE + new java.util.Date(v.timestampMs));
            if (v.details != null && !v.details.isEmpty()) {
                lore.add(ChatColor.GRAY + v.details);
            }
            lore.add("");
            lore.add(ChatColor.GREEN + "LEFT click = aprobar ban");
            lore.add(ChatColor.RED   + "RIGHT click = rechazar");
            meta.setLore(lore);
            it.setItemMeta(meta);
            inv.setItem(slot++, it);
        }
    }

    @Override
    public Inventory getInventory() { return inv; }
}
