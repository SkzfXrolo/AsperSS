package com.argusprojects.argusmc.anticheat.packet;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;

import java.util.logging.Level;

public final class PacketEventsBootstrap {

    private final ArgusPlugin plugin;
    private boolean available = false;
    private boolean initialized = false;
    private PacketAnticheatListener listener;
    private PacketDataStore dataStore;

    public PacketEventsBootstrap(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public boolean detect() {
        try {
            if (Bukkit.getPluginManager().getPlugin("packetevents") == null) {
                plugin.getLogger().info("[Argus/Packet] PacketEvents NO detectado. "
                    + "El anti-cheat sigue activo con detecciones Bukkit-based. "
                    + "Para mejor precision (reach/killaura/timer/phase/pingspoof), "
                    + "instala PacketEvents: https://www.spigotmc.org/resources/packetevents.80279/");
                this.available = false;
                return false;
            }

            Class.forName("com.github.retrooper.packetevents.PacketEvents");
            this.available = true;
            plugin.getLogger().info("[Argus/Packet] PacketEvents detectado. Inicializando anti-cheat packet-based...");
            return true;
        } catch (Throwable t) {
            plugin.getLogger().log(Level.WARNING,
                "[Argus/Packet] PacketEvents presente pero version incompatible. Usando fallback Bukkit. Causa: "
                    + t.getMessage());
            this.available = false;
            return false;
        }
    }

    public boolean init() {
        if (!available) return false;
        if (initialized) return true;
        try {
            if (!PacketEventsRegistrar.isApiReady()) {
                plugin.getLogger().warning("[Argus/Packet] PacketEvents.getAPI() aun null. Reintentando en 5s.");
                Bukkit.getScheduler().runTaskLater(plugin, this::init, 100L);
                return false;
            }
            this.dataStore = new PacketDataStore();
            EntitySnapshot entities = new EntitySnapshot();
            Bukkit.getScheduler().runTaskTimer(plugin, entities, 1L, 1L);
            this.listener  = new PacketAnticheatListener(plugin, dataStore, entities);

            PacketEventsRegistrar.register(listener);

            Bukkit.getPluginManager().registerEvents(
                new PacketAnticheatBukkitBridge(plugin, dataStore, listener), plugin);

            initialized = true;
            plugin.getLogger().info("[Argus/Packet] checks packet-based activos: timer, phase, velocity, "
                + "invalid_rotation, reach_packet, killaura_swing_packet, aim_snap_packet, "
                + "ping_spoof, cps_packet, inv_move_packet, vclip, step, speed_packet, "
                + "fast_place, fast_break, nuker, auto_totem");
            return true;
        } catch (Throwable t) {
            plugin.getLogger().log(Level.WARNING,
                "[Argus/Packet] Fallo inicializando packet listener. Fallback Bukkit activo. Causa: " + t, t);
            this.available = false;
            return false;
        }
    }

    public void shutdown() {
        if (listener != null && initialized) {
            try {
                PacketEventsRegistrar.unregister(listener);
            } catch (Throwable ignored) {

            }
        }
        initialized = false;
    }

    public boolean isAvailable()      { return available; }
    public boolean isInitialized()    { return initialized; }
    public PacketDataStore getDataStore() { return dataStore; }
}
