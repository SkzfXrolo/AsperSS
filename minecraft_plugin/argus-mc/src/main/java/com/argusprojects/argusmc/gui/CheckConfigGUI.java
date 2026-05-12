package com.argusprojects.argusmc.gui;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Pack 48 round 3 — GUI runtime para editar thresholds de checks.
 *
 * <p>Muestra cada check como un ítem; al click izquierdo escribe el
 * threshold en chat para que el admin pueda copiar; al click derecho
 * abre una sub-vista con los key=value del check. Es un VIEW-ONLY GUI
 * por ahora — las mutaciones se hacen via {@code /argus admin set}
 * (no implementado aquí para mantener scope y safety).
 */
public final class CheckConfigGUI implements InventoryHolder {

    private final Inventory inv;

    public static void open(ArgusPlugin plugin, Player viewer) {
        CheckConfigGUI gui = new CheckConfigGUI(plugin);
        viewer.openInventory(gui.inv);
    }

    private CheckConfigGUI(ArgusPlugin plugin) {
        ConfigurationSection root = plugin.getConfig()
            .getConfigurationSection("anticheat.checks");
        List<String> names = root == null ? Collections.emptyList()
            : new ArrayList<>(root.getKeys(false));
        Collections.sort(names);

        int size = (int) Math.ceil(names.size() / 9.0) * 9;
        if (size < 9) size = 9;
        if (size > 54) size = 54;
        this.inv = Bukkit.createInventory(this, size,
            ChatColor.DARK_AQUA + "Argus » Checks Config");

        int slot = 0;
        for (String name : names) {
            if (slot >= size) break;
            ConfigurationSection sec = root.getConfigurationSection(name);
            boolean enabled = sec != null && sec.getBoolean("enabled", true);
            ItemStack it = new ItemStack(enabled ? Material.LIME_DYE : Material.GRAY_DYE);
            ItemMeta meta = it.getItemMeta();
            meta.setDisplayName(ChatColor.WHITE + name + (enabled
                ? " " + ChatColor.GREEN + "ON" : " " + ChatColor.GRAY + "OFF"));
            List<String> lore = new ArrayList<>();
            if (sec != null) {
                for (String k : sec.getKeys(false)) {
                    if (k.equals("enabled")) continue;
                    lore.add(ChatColor.GRAY + k + ": " + ChatColor.WHITE + sec.get(k));
                    if (lore.size() >= 8) break;
                }
            }
            lore.add("");
            lore.add(ChatColor.YELLOW + "/argus admin set " + name + " <key> <val>");
            meta.setLore(lore);
            it.setItemMeta(meta);
            inv.setItem(slot++, it);
        }
    }

    @Override
    public Inventory getInventory() { return inv; }
}
