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
 * Pack 48 round 3 — Vista de stats del Oracle ML.
 *
 * <p>Muestra:
 * <ul>
 *   <li>Estado on/off del Oracle.</li>
 *   <li>Cache size del LRU.</li>
 *   <li>URL configurada (truncada).</li>
 *   <li>Última weight observada (placeholder).</li>
 * </ul>
 *
 * <p>Es una vista informacional; los datos reales viven en
 * {@code OracleCache} (in-memory) — la wirebase completa requiere
 * exponer el OracleCache via plugin singleton (next pack).
 */
public final class OracleStatsGUI implements InventoryHolder {

    private final Inventory inv;

    public static void open(ArgusPlugin plugin, Player viewer) {
        OracleStatsGUI gui = new OracleStatsGUI(plugin);
        viewer.openInventory(gui.inv);
    }

    private OracleStatsGUI(ArgusPlugin plugin) {
        this.inv = Bukkit.createInventory(this, 27,
            ChatColor.LIGHT_PURPLE + "Argus » Oracle Stats");

        var sec = plugin.getConfig().getConfigurationSection("oracle");
        boolean enabled = sec != null && sec.getBoolean("enabled", false);
        String url = sec == null ? "" : sec.getString("url", "");
        long timeoutMs = sec == null ? 0L : sec.getLong("timeout_ms", 1500L);
        long ttlMs     = sec == null ? 0L : sec.getLong("cache_ttl_ms", 30_000L);

        inv.setItem(11, info(enabled ? Material.LIME_DYE : Material.GRAY_DYE,
            "Oracle: " + (enabled ? ChatColor.GREEN + "ON" : ChatColor.RED + "OFF"),
            "Click izquierdo: cycle on/off (requiere reload)"));

        inv.setItem(13, info(Material.PAPER, "URL",
            url.isEmpty() ? ChatColor.GRAY + "<sin configurar>"
                          : ChatColor.WHITE + truncate(url, 38)));

        inv.setItem(15, info(Material.CLOCK, "Timeout / TTL",
            ChatColor.WHITE + (timeoutMs + "ms / " + (ttlMs / 1000) + "s")));

        inv.setItem(22, info(Material.BOOK, "Cómo activar",
            ChatColor.GRAY + "Edit config.yml::oracle.enabled=true",
            ChatColor.GRAY + "Set url + api_key + /argus admin reload"));
    }

    @Override
    public Inventory getInventory() { return inv; }

    private static ItemStack info(Material m, String title, String... loreLines) {
        ItemStack it = new ItemStack(m);
        ItemMeta meta = it.getItemMeta();
        meta.setDisplayName(ChatColor.WHITE + title);
        List<String> lore = new ArrayList<>();
        for (String l : loreLines) lore.add(l);
        meta.setLore(lore);
        it.setItemMeta(meta);
        return it;
    }

    private static String truncate(String s, int max) {
        if (s == null) return "";
        if (s.length() <= max) return s;
        return s.substring(0, max - 1) + "…";
    }
}
