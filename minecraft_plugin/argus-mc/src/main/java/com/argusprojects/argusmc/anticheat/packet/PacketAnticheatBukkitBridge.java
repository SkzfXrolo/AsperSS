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
        s.selectedSlot = e.getPlayer().getInventory().getHeldItemSlot();
        s.lastX = e.getPlayer().getLocation().getX();
        s.lastY = e.getPlayer().getLocation().getY();
        s.lastZ = e.getPlayer().getLocation().getZ();
        s.teleporting = true;
        s.teleportUntilMs = System.currentTimeMillis() + 5_000L;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onQuit(PlayerQuitEvent e) {
        store.remove(e.getPlayer().getUniqueId());
        plugin.getAutoClickEngine().remove(e.getPlayer().getUniqueId());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onTeleport(PlayerTeleportEvent e) {
        PacketDataStore.State s = store.get(e.getPlayer().getUniqueId());
        s.teleporting = true;
        s.teleportUntilMs = System.currentTimeMillis() + 1_500L;
    }

    /** Reaparecer y cambiar de mundo mueven al jugador sin PlayerTeleportEvent: mismo grace que un teleport. */
    @EventHandler(priority = EventPriority.MONITOR)
    public void onRespawn(org.bukkit.event.player.PlayerRespawnEvent e) {
        PacketDataStore.State s = store.get(e.getPlayer().getUniqueId());
        s.teleporting = true;
        s.teleportUntilMs = System.currentTimeMillis() + 1_500L;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onWorldChange(org.bukkit.event.player.PlayerChangedWorldEvent e) {
        PacketDataStore.State s = store.get(e.getPlayer().getUniqueId());
        s.teleporting = true;
        s.teleportUntilMs = System.currentTimeMillis() + 1_500L;
    }

    /** Al bajarse, el server reubica al jugador junto al vehiculo: equivale a un teleport. */
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onVehicleExit(org.bukkit.event.vehicle.VehicleExitEvent e) {
        if (!(e.getExited() instanceof org.bukkit.entity.Player p)) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
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

        double mag = Math.sqrt(s.serverVelX * s.serverVelX + s.serverVelZ * s.serverVelZ);
        s.kbX = s.serverVelX;
        s.kbY = s.serverVelY;
        s.kbZ = s.serverVelZ;
        s.kbAtMs = s.serverVelAssignedAtMs;
        s.kbBestAlong = Double.NEGATIVE_INFINITY;
        s.kbBestDy = Double.NEGATIVE_INFINITY;
        s.kbPending = mag >= 0.2 || s.serverVelY >= 0.25;
        if (mag > 0.05) {
            s.lastKnockbackExpectedMs  = s.serverVelAssignedAtMs;
            s.lastKnockbackExpectedMag = mag;
        }
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onInvOpen(InventoryOpenEvent e) {
        if (!(e.getPlayer() instanceof org.bukkit.entity.Player p)) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        s.inventoryOpen = true;
        s.inventoryOpenSinceMs = System.currentTimeMillis();
        s.invFirstClickPending = true;
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onInvClose(InventoryCloseEvent e) {
        if (!(e.getPlayer() instanceof org.bukkit.entity.Player p)) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        s.inventoryOpen = false;
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onDamage(EntityDamageEvent e) {
        if (!(e.getEntity() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        s.lastDamageTakenMs = System.currentTimeMillis();

        s.lastDamageHealthAfter = Math.max(0.0, p.getHealth() - e.getFinalDamage());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSwapHands(PlayerSwapHandItemsEvent e) {
        org.bukkit.entity.Player p = e.getPlayer();
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());

        ItemStack offhandAfter = e.getOffHandItem();
        Bukkit.getScheduler().runTaskLater(plugin, () ->
            listener.getAutoTotemCheck().handleOffhandUpdate(
                p, s, System.currentTimeMillis(), offhandAfter, listener.getSink()), 1L);
    }

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
        if (!(e.getHitEntity() instanceof org.bukkit.entity.Player)) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        listener.getProjectileAimCheck().handleHit(p, e.getEntity(), s, listener.getSink());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onShootBow(EntityShootBowEvent e) {
        if (!(e.getEntity() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        long now = System.currentTimeMillis();
        listener.getBowAimCheck().handleShoot(p, s, now, listener.getSink());
        listener.getBowAimbotCheck().onShoot(p, listener.getSink());

        long chargeMs = s.useItemStartMs == 0L ? 0L : (now - s.useItemStartMs);
        listener.getFastBowCheck().handleBowShoot(p, s, chargeMs, e.getForce(), listener.getSink());
        s.useItemStartMs = 0L;
        s.useItemMaterial = null;
    }

    // Sin ignoreCancelled: Bukkit marca RIGHT_CLICK_AIR como cancelado (no hay bloque que usar)
    // aunque el item SI se use. Lo que importa es useItemInHand.
    @EventHandler(priority = EventPriority.MONITOR)
    public void onInteract(org.bukkit.event.player.PlayerInteractEvent e) {
        org.bukkit.entity.Player p = e.getPlayer();
        if (e.useItemInHand() == org.bukkit.event.Event.Result.DENY) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        if (e.getAction() != org.bukkit.event.block.Action.RIGHT_CLICK_AIR
            && e.getAction() != org.bukkit.event.block.Action.RIGHT_CLICK_BLOCK) return;
        ItemStack item = e.getItem();
        if (item == null) return;
        org.bukkit.Material m = item.getType();

        boolean tracked = m.isEdible()
            || m == org.bukkit.Material.BOW
            || m == org.bukkit.Material.CROSSBOW
            || m == org.bukkit.Material.SHIELD
            || m == org.bukkit.Material.POTION
            || m == org.bukkit.Material.SPLASH_POTION
            || m == org.bukkit.Material.LINGERING_POTION
            || m == org.bukkit.Material.MILK_BUCKET
            || m == org.bukkit.Material.GOAT_HORN;
        if (!tracked) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        long now = System.currentTimeMillis();
        // Click repetido mientras ya usa el item (1.8): no reinicia el tiempo de uso.
        if (p.isHandRaised() && s.useItemStartMs != 0L && m.name().equals(s.useItemMaterial)) return;
        s.useItemStartMs  = now;
        s.useItemMaterial = m.name();
        if (m == org.bukkit.Material.BOW) listener.getBowAimbotCheck().startDraw(p);
        listener.getAutoPotionCheck().handleUseStart(p, s, m.name(), now, listener.getSink());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onItemConsume(org.bukkit.event.player.PlayerItemConsumeEvent e) {
        org.bukkit.entity.Player p = e.getPlayer();
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        long now = System.currentTimeMillis();
        listener.getFastEatCheck().handleEatFinish(p, s, now, listener.getSink());
        listener.getAutoEatCheck().handleEatFinish(p, s, now, listener.getSink());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onSneak(org.bukkit.event.player.PlayerToggleSneakEvent e) {
        org.bukkit.entity.Player p = e.getPlayer();
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        s.sneakActive = e.isSneaking();
        if (e.isSneaking()) s.sneakStartMs = System.currentTimeMillis();
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onArmorChange(org.bukkit.event.inventory.InventoryClickEvent e) {
        if (!(e.getWhoClicked() instanceof org.bukkit.entity.Player p)) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        int slot = e.getSlot();

        if (e.getSlotType() != org.bukkit.event.inventory.InventoryType.SlotType.ARMOR
            && (slot < 36 || slot > 39)) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        Bukkit.getScheduler().runTask(plugin, () ->
            listener.getAutoArmorCheck().handleArmorChange(p, s,
                System.currentTimeMillis(), listener.getSink()));
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onRegen(org.bukkit.event.entity.EntityRegainHealthEvent e) {
        if (!(e.getEntity() instanceof org.bukkit.entity.Player p)) return;
        // Pociones, manzanas, beacons y plugins curan legitimamente a cualquier ritmo;
        // solo la regen natural por saciedad tiene un techo vanilla medible (1hp/10 ticks).
        if (e.getRegainReason() != org.bukkit.event.entity.EntityRegainHealthEvent.RegainReason.SATIATED) return;
        if (p.hasPermission("argus.ac.bypass")) return;
        PacketDataStore.State s = store.get(p.getUniqueId());
        long now = System.currentTimeMillis();
        // Solo la cantidad de esta cura: entre dos regens naturales puede haber curas de pociones.
        s.lastHealth = p.getHealth();
        listener.getRegenCheck().handleHealthChange(p, s, p.getHealth() + e.getAmount(), now, listener.getSink());
    }

    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onResourcePackStatus(org.bukkit.event.player.PlayerResourcePackStatusEvent e) {

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

        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            try {
                ItemStack offhand = p.getInventory().getItemInOffHand();
                listener.getAutoTotemCheck().handleOffhandUpdate(
                    p, s, System.currentTimeMillis(), offhand, listener.getSink());
            } catch (Throwable ignored) {}
        }, 1L);
    }
}
