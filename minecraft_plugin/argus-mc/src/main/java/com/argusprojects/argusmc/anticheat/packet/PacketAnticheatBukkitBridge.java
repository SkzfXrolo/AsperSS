package com.argusprojects.argusmc.anticheat.packet;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.entity.EntityDamageByEntityEvent;
import org.bukkit.event.entity.EntityDamageEvent;
import org.bukkit.event.entity.EntityPickupItemEvent;
import org.bukkit.event.entity.EntityShootBowEvent;
import org.bukkit.event.entity.ProjectileHitEvent;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.AsyncPlayerChatEvent;
import org.bukkit.event.player.PlayerItemHeldEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.event.player.PlayerVelocityEvent;
import org.bukkit.inventory.ItemStack;

/**
 * Pack 47 — Bridge entre eventos Bukkit y el {@link PacketDataStore}.
 *
 * <p>Algunos datos viven naturalmente en eventos Bukkit y no en packets:
 * <ul>
 *   <li>{@link PlayerVelocityEvent}: el server ASIGNA velocity al cliente (knockback).
 *       Lo guardamos para que {@code VelocityCheck} compare contra el movimiento
 *       que el cliente envia en los proximos ticks.</li>
 *   <li>{@link PlayerTeleportEvent}: marca al jugador como "teleporting" durante
 *       1 segundo para que los checks de movement ignoren ese intervalo.</li>
 *   <li>{@link InventoryOpenEvent}/{@link InventoryCloseEvent}: estado de
 *       inventario abierto, usado por {@code InvMovePacketCheck}.</li>
 *   <li>{@link PlayerJoinEvent}/{@link PlayerQuitEvent}: lifecycle del state.</li>
 * </ul>
 */
public final class PacketAnticheatBukkitBridge implements Listener {

    private final ArgusPlugin plugin;
    private final PacketDataStore store;
    private final PacketAnticheatListener listener;

    public PacketAnticheatBukkitBridge(ArgusPlugin plugin, PacketDataStore store, PacketAnticheatListener listener) {
        this.plugin = plugin;
        this.store = store;
        this.listener = listener;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onJoin(PlayerJoinEvent e) {
        PacketDataStore.State s = store.get(e.getPlayer().getUniqueId());
        s.joinMs = System.currentTimeMillis();
        s.lastX = e.getPlayer().getLocation().getX();
        s.lastY = e.getPlayer().getLocation().getY();
        s.lastZ = e.getPlayer().getLocation().getZ();
        s.teleporting = true;
        s.teleportUntilMs = System.currentTimeMillis() + 5_000L;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        store.remove(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        PacketDataStore.State s = store.get(e.getPlayer().getUniqueId());
        s.teleporting = true;
        s.teleportUntilMs = System.currentTimeMillis() + 1_500L;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onVelocity(PlayerVelocityEvent e) {
        PacketDataStore.State s = store.get(e.getPlayer().getUniqueId());
        s.serverVelX = e.getVelocity().getX();
        s.serverVelY = e.getVelocity().getY();
        s.serverVelZ = e.getVelocity().getZ();
        s.serverVelAssignedAtMs = System.currentTimeMillis();
        s.serverVelConsumed = false;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onInvOpen(InventoryOpenEvent e) {
        if (!(e.getPlayer() instanceof org.bukkit.entity.Player p)) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        s.inventoryOpen = true;
        s.inventoryOpenSinceMs = System.currentTimeMillis();
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInvClose(InventoryCloseEvent e) {
        if (!(e.getPlayer() instanceof org.bukkit.entity.Player p)) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        s.inventoryOpen = false;
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Pack 48 #488 — AutoTotem: tracking de damage + inventory swap.
    // ──────────────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        s.lastDamageTakenMs = System.currentTimeMillis();
        // health DESPUES del damage (puede ser negativa si totem ya activo).
        s.lastDamageHealthAfter = Math.max(0.0, p.getHealth() - e.getFinalDamage());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwapHands(PlayerSwapHandItemsEvent e) {
        org.bukkit.entity.Player p = e.getPlayer();
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        // El offhand resultante despues del swap es el item que estaba en main.
        ItemStack offhandAfter = e.getOffHandItem();
        Bukkit.getScheduler().runTaskLater(plugin, () ->
            listener.getAutoTotemCheck().handleOffhandUpdate(
                p, s, System.currentTimeMillis(), offhandAfter, listener.getSink()), 1L);
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Round 2 — Crit / ProjectileAim / BowAim via eventos Bukkit.
    // ──────────────────────────────────────────────────────────────────────

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onCombatDamage(EntityDamageByEntityEvent e) {
        if (!(e.getDamager() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        listener.getCritCheck().handleDamage(p, s, e, listener.getSink());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onProjectileHit(ProjectileHitEvent e) {
        if (!(e.getEntity().getShooter() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        if (!(e.getHitEntity() instanceof org.bukkit.entity.Player)) return; // solo si hit a otro player
        PacketDataStore.State s = store.get(p.getUniqueId());
        listener.getProjectileAimCheck().handleHit(p, e.getEntity(), s, listener.getSink());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onShootBow(EntityShootBowEvent e) {
        if (!(e.getEntity() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        listener.getBowAimCheck().handleShoot(p, s, System.currentTimeMillis(), listener.getSink());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPickup(EntityPickupItemEvent e) {
        if (!(e.getEntity() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        listener.getItemPickupCheck().handlePickup(p, e.getItem(), s, listener.getSink());
    }

    @SuppressWarnings("deprecation")
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onChat(AsyncPlayerChatEvent e) {
        org.bukkit.entity.Player p = e.getPlayer();
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        listener.getChatMacroCheck().handleChat(p, s, e.getMessage(), System.currentTimeMillis(), listener.getSink());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onItemHeld(PlayerItemHeldEvent e) {
        org.bukkit.entity.Player p = e.getPlayer();
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        Bukkit.getScheduler().runTaskLater(plugin, () ->
            listener.getNamedItemSpamCheck().handleHeldItemChange(p, s,
                System.currentTimeMillis(), listener.getSink()), 1L);
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onInvClick(InventoryClickEvent e) {
        if (!(e.getWhoClicked() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        // El offhand del inventario del player es slot 40 (PlayerInventory).
        // Verificamos en el siguiente tick (post-update) si quedo un totem ahi.
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            try {
                ItemStack offhand = p.getInventory().getItemInOffHand();
                listener.getAutoTotemCheck().handleOffhandUpdate(
                    p, s, System.currentTimeMillis(), offhand, listener.getSink());
            } catch (Throwable ignored) {}
        }, 1L);
    }
}
