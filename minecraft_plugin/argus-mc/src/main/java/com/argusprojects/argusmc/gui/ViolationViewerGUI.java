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
import java.util.UUID;

/**
 * Pack 48 round 3 — Visor de violations por jugador (chest GUI).
 *
 * <p>Abre con {@code /argus admin viewer &lt;player&gt;} y muestra las
 * últimas 54 violations del player en chest 54-slot, una por slot,
 * material según severidad:
 * <ul>
 *   <li>LOW → wool gris</li>
 *   <li>MID → wool amarillo</li>
 *   <li>HIGH → wool naranja</li>
 *   <li>CRITICAL → wool rojo</li>
 * </ul>
 */
public final class ViolationViewerGUI implements InventoryHolder {

    private final Inventory inv;

    public static void open(ArgusPlugin plugin, Player viewer, String targetName) {
        UUID target = null;
        Player tp = Bukkit.getPlayerExact(targetName);
        if (tp != null) target = tp.getUniqueId();
        ViolationViewerGUI gui = new ViolationViewerGUI(plugin, targetName, target);
        viewer.openInventory(gui.inv);
    }

    private ViolationViewerGUI(ArgusPlugin plugin, String targetName, UUID targetUuid) {
        this.inv = Bukkit.createInventory(this, 54,
            ChatColor.DARK_AQUA + "Argus » Viol " + ChatColor.WHITE + targetName);
        var vm = plugin.getViolationManager();
        if (vm == null) return;
        var all = vm.snapshotGlobalRecent(200);
        int slot = 0;
        for (int i = all.size() - 1; i >= 0 && slot < 54; i--) {
            var v = all.get(i);
            if (targetUuid != null && !targetUuid.equals(v.playerUuid)) continue;
            inv.setItem(slot++, render(v));
        }
    }

    @Override
    public Inventory getInventory() { return inv; }

    private static ItemStack render(com.argusprojects.argusmc.anticheat.Violation v) {
        Material m;
        switch (v.level) {
            case CRITICAL: m = Material.RED_WOOL;    break;
            case HIGH:     m = Material.ORANGE_WOOL; break;
            case MID:      m = Material.YELLOW_WOOL; break;
            default:       m = Material.LIGHT_GRAY_WOOL;
        }
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.setDisplayName(ChatColor.WHITE + v.checkName + " "
            + ChatColor.GRAY + "[" + v.level + "]");
        List<String> lore = new ArrayList<>();
        lore.add(ChatColor.GRAY + "Player: " + ChatColor.WHITE + v.playerName);
        lore.add(ChatColor.GRAY + "Time: " + ChatColor.WHITE + new java.util.Date(v.timestampMs));
        if (v.details != null && !v.details.isEmpty()) {
            // Wrap detail at ~40 chars.
            for (int i = 0; i < v.details.length(); i += 40) {
                lore.add(ChatColor.GRAY + v.details.substring(i, Math.min(i + 40, v.details.length())));
            }
        }
        meta.setLore(lore);
        it.setItemMeta(meta);
        return it;
    }
}
