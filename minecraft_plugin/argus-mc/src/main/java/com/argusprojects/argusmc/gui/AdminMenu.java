package com.argusprojects.argusmc.gui;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.SkullMeta;

import java.util.ArrayList;
import java.util.List;

/**
 * Pack 48 round 2 — Admin chest GUI.
 *
 * <p>Menu de administracion in-game accesible via {@code /argus admin menu}.
 * Tres niveles:
 * <ol>
 *   <li><b>Root</b> (27 slots) — overview con stats, lista de players (cabezas)
 *       y settings rapidos.</li>
 *   <li><b>Player detail</b> (27 slots) — datos del jugador clickeado.</li>
 *   <li><b>Check toggle</b> (54 slots) — activa/desactiva checks individuales.</li>
 * </ol>
 *
 * <p>Como detectar clicks: implementamos {@link InventoryHolder} para que el
 * inventario sepa que es nuestro, y registramos esta clase como Listener.
 */
public final class AdminMenu implements InventoryHolder, Listener {

    public enum View { ROOT, PLAYER, CHECK_TOGGLE }

    private static final String ROOT_TITLE   = ChatColor.DARK_AQUA + "Argus Admin";
    private static final String PLAYER_TITLE = ChatColor.DARK_AQUA + "Argus » Player";
    private static final String CHECK_TITLE  = ChatColor.DARK_AQUA + "Argus » Checks";

    private final ArgusPlugin plugin;
    private final Inventory inventory;
    private final View view;
    private String targetPlayerName;

    /** Abre el menu root para un admin. */
    public static void open(ArgusPlugin plugin, Player admin) {
        AdminMenu menu = new AdminMenu(plugin, View.ROOT, null);
        menu.populate();
        admin.openInventory(menu.inventory);
    }

    public AdminMenu(ArgusPlugin plugin, View view, String targetPlayerName) {
        this.plugin = plugin;
        this.view = view;
        this.targetPlayerName = targetPlayerName;
        int size;
        String title;
        switch (view) {
            case ROOT:         size = 27; title = ROOT_TITLE; break;
            case PLAYER:       size = 27; title = PLAYER_TITLE + " " + ChatColor.GRAY + targetPlayerName; break;
            case CHECK_TOGGLE: size = 54; title = CHECK_TITLE; break;
            default:           size = 27; title = ROOT_TITLE; break;
        }
        this.inventory = Bukkit.createInventory(this, size, title);
    }

    @Override
    public Inventory getInventory() { return inventory; }

    public View getView() { return view; }
    public String getTargetPlayerName() { return targetPlayerName; }

    private void populate() {
        switch (view) {
            case ROOT:         populateRoot(); break;
            case PLAYER:       populatePlayer(); break;
            case CHECK_TOGGLE: populateCheckToggle(); break;
        }
    }

    private void populateRoot() {
        // Stats item (compass)
        int onlineCount = Bukkit.getOnlinePlayers().size();
        int totalVios = 0;
        for (Player p : Bukkit.getOnlinePlayers()) {
            totalVios += plugin.getViolationManager().countRecent(p.getUniqueId());
        }
        ItemStack stats = named(Material.COMPASS,
            ChatColor.AQUA + "Stats",
            ChatColor.GRAY + "Players online: " + ChatColor.WHITE + onlineCount,
            ChatColor.GRAY + "Violations (window): " + ChatColor.YELLOW + totalVios,
            "",
            ChatColor.GRAY + "Click: " + ChatColor.WHITE + "refresh");
        inventory.setItem(4, stats);

        // Player heads (slots 9..17 hasta 9 jugadores)
        int slot = 9;
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (slot >= 18) break;
            ItemStack head = playerHead(p.getName(),
                ChatColor.AQUA + p.getName(),
                ChatColor.GRAY + "Violations: " + ChatColor.YELLOW
                    + plugin.getViolationManager().countRecent(p.getUniqueId()),
                ChatColor.GRAY + "Ping: " + ChatColor.WHITE + p.getPing() + "ms",
                "",
                ChatColor.YELLOW + "Click: " + ChatColor.WHITE + "ver detalle");
            inventory.setItem(slot++, head);
        }

        // Checks toggle
        ItemStack checks = named(Material.REDSTONE_TORCH,
            ChatColor.AQUA + "Checks",
            ChatColor.GRAY + "Toggle on/off individual",
            ChatColor.GRAY + "(round 2: pseudo, requiere reload)");
        inventory.setItem(22, checks);

        // Cerrar
        ItemStack close = named(Material.BARRIER, ChatColor.RED + "Cerrar");
        inventory.setItem(26, close);
    }

    private void populatePlayer() {
        Player target = targetPlayerName != null ? Bukkit.getPlayerExact(targetPlayerName) : null;
        if (target == null) {
            inventory.setItem(13, named(Material.BARRIER, ChatColor.RED + "Jugador offline"));
            return;
        }
        int vios = plugin.getViolationManager().countRecent(target.getUniqueId());
        ItemStack head = playerHead(target.getName(),
            ChatColor.AQUA + target.getName(),
            ChatColor.GRAY + "UUID: " + ChatColor.WHITE + target.getUniqueId().toString().substring(0, 8) + "…",
            ChatColor.GRAY + "Game mode: " + ChatColor.WHITE + target.getGameMode().name(),
            ChatColor.GRAY + "Ping: " + ChatColor.WHITE + target.getPing() + "ms",
            ChatColor.GRAY + "Violations (window): " + ChatColor.YELLOW + vios);
        inventory.setItem(4, head);

        ItemStack clear = named(Material.WATER_BUCKET,
            ChatColor.AQUA + "Clear violations",
            ChatColor.GRAY + "Click: limpia violations + buffers");
        inventory.setItem(11, clear);

        ItemStack kick = named(Material.IRON_BOOTS,
            ChatColor.AQUA + "Kick",
            ChatColor.GRAY + "Click: kickea al jugador (motivo: review staff)");
        inventory.setItem(13, kick);

        ItemStack ss = named(Material.SPYGLASS,
            ChatColor.AQUA + "Screen Share",
            ChatColor.GRAY + "Click: emite token de SS (sin razon)");
        inventory.setItem(15, ss);

        ItemStack back = named(Material.ARROW, ChatColor.YELLOW + "« Volver");
        inventory.setItem(22, back);
    }

    private void populateCheckToggle() {
        var ac = plugin.getAnticheatConfig();
        String[] checks = {
            "timer","phase","velocity","invalid_rotation","reach_packet","killaura_swing_packet",
            "aim_snap_packet","ping_spoof","cps_packet","inv_move_packet",
            "vclip","step","speed_packet","fast_place","fast_break","nuker","auto_totem",
            "killaura_aim","killaura_blocking","boat_fly","jetpack","spider",
            "multi_velocity","block_reach","crit","projectile_aim","bow_aim","boat_fly_advanced",
            "hitbox_expansion","backstab","melee_fly",
            "block_glitch","item_pickup","inventory_teleport","liquid_walk",
            "chat_macro","named_item_spam","autoclicker_advanced"
        };
        int slot = 0;
        for (String c : checks) {
            if (slot >= 53) break;
            boolean enabled = ac == null || ac.isCheckEnabled(c);
            Material m = enabled ? Material.LIME_DYE : Material.GRAY_DYE;
            ItemStack it = named(m,
                (enabled ? ChatColor.GREEN : ChatColor.GRAY) + c,
                ChatColor.GRAY + "Estado: " + (enabled ? ChatColor.GREEN + "ON" : ChatColor.RED + "OFF"),
                ChatColor.GRAY + "(click: editar en config.yml)");
            inventory.setItem(slot++, it);
        }
        inventory.setItem(53, named(Material.ARROW, ChatColor.YELLOW + "« Volver"));
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Eventos
    // ──────────────────────────────────────────────────────────────────────

    @EventHandler
    public void onClick(InventoryClickEvent e) {
        if (!(e.getInventory().getHolder() instanceof AdminMenu menu)) return;
        e.setCancelled(true);
        if (!(e.getWhoClicked() instanceof Player admin)) return;

        int slot = e.getRawSlot();
        ItemStack clicked = e.getCurrentItem();
        if (clicked == null) return;

        switch (menu.view) {
            case ROOT: {
                if (slot == 26) { admin.closeInventory(); return; }
                if (slot == 4)  { AdminMenu.open(plugin, admin); return; } // refresh
                if (slot == 22) {
                    AdminMenu sub = new AdminMenu(plugin, View.CHECK_TOGGLE, null);
                    sub.populate();
                    admin.openInventory(sub.inventory);
                    return;
                }
                if (slot >= 9 && slot < 18 && clicked.getType() == Material.PLAYER_HEAD) {
                    ItemMeta meta = clicked.getItemMeta();
                    if (meta != null) {
                        String name = ChatColor.stripColor(meta.getDisplayName());
                        AdminMenu sub = new AdminMenu(plugin, View.PLAYER, name);
                        sub.populate();
                        admin.openInventory(sub.inventory);
                    }
                }
                break;
            }
            case PLAYER: {
                Player target = menu.targetPlayerName != null
                    ? Bukkit.getPlayerExact(menu.targetPlayerName) : null;
                if (slot == 22) { AdminMenu.open(plugin, admin); return; }
                if (target == null) return;
                if (slot == 11) {
                    plugin.getViolationManager().clearViolations(target.getUniqueId());
                    var bs = plugin.getPacketEventsBootstrap();
                    if (bs != null && bs.getDataStore() != null) {
                        var s = bs.getDataStore().peek(target.getUniqueId());
                        if (s != null) s.clearTransient();
                    }
                    admin.sendMessage(ChatColor.GREEN + "Violations limpiadas para " + target.getName());
                } else if (slot == 13) {
                    target.kickPlayer(ChatColor.RED + "Kick por staff via Argus admin menu.");
                    admin.sendMessage(ChatColor.YELLOW + "Kick ejecutado.");
                    AdminMenu.open(plugin, admin);
                } else if (slot == 15) {
                    Bukkit.dispatchCommand(admin, "argus check " + target.getName() + " review via menu");
                }
                break;
            }
            case CHECK_TOGGLE: {
                if (slot == 53) { AdminMenu.open(plugin, admin); return; }
                // Toggle real requeriria escribir config.yml — fuera de scope round 2.
                admin.sendMessage(ChatColor.YELLOW + "Edita anticheat.checks.<name>.enabled en config.yml y usa /argus reload.");
                break;
            }
        }
    }

    @EventHandler
    public void onClose(InventoryCloseEvent e) {
        // no-op por ahora.
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Helpers
    // ──────────────────────────────────────────────────────────────────────

    private static ItemStack named(Material m, String name, String... lore) {
        ItemStack s = new ItemStack(m);
        ItemMeta meta = s.getItemMeta();
        if (meta != null) {
            meta.setDisplayName(name);
            if (lore != null && lore.length > 0) {
                List<String> list = new ArrayList<>();
                for (String l : lore) list.add(l);
                meta.setLore(list);
            }
            s.setItemMeta(meta);
        }
        return s;
    }

    private static ItemStack playerHead(String playerName, String name, String... lore) {
        ItemStack s = new ItemStack(Material.PLAYER_HEAD);
        ItemMeta meta = s.getItemMeta();
        if (meta instanceof SkullMeta sm) {
            try {
                sm.setOwningPlayer(Bukkit.getOfflinePlayer(playerName));
            } catch (Throwable ignored) {}
        }
        if (meta != null) {
            meta.setDisplayName(name);
            if (lore != null && lore.length > 0) {
                List<String> list = new ArrayList<>();
                for (String l : lore) list.add(l);
                meta.setLore(list);
            }
            s.setItemMeta(meta);
        }
        return s;
    }
}
