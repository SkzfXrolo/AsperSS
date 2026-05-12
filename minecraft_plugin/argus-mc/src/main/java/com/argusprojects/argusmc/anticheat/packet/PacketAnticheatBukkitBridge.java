package com.argusprojects.argusmc.anticheat.packet;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryCloseEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.player.PlayerTeleportEvent;
import org.bukkit.event.player.PlayerVelocityEvent;

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
    @SuppressWarnings("unused") // referencia retenida para futuras integraciones
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
}
