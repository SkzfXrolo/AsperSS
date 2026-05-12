package com.argusprojects.argusmc.anticheat.packet;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;

import java.util.logging.Level;

/**
 * Pack 47 — Bootstrap del modulo packet-based.
 *
 * <p>PacketEvents es soft-dependency: si el plugin no esta instalado en el
 * server, ArgusMC sigue funcionando con su {@code AnticheatListener} Bukkit-based.
 * Si esta instalado, este bootstrap engancha el {@link PacketAnticheatListener}
 * que se suscribe a packets crudos (movement, combat, click, timing) y
 * desbloquea checks imposibles desde Bukkit events (TimerHack, Phase, PingSpoof,
 * Reach exacto a nivel packet, Killaura swing por timestamp, etc.).
 *
 * <p>Diseño defensivo: TODA interaccion con PacketEvents pasa por reflection
 * y try/catch generoso. Si el server tiene una version incompatible o si la
 * API cambia, ArgusMC NO crashea — solo loguea WARNING y opera con el
 * fallback Bukkit-based.
 *
 * <p>El bootstrap NO importa clases de PacketEvents en sus campos para que la
 * JVM no falle con ClassNotFoundException al cargar este archivo cuando
 * PacketEvents no esta presente. Las clases se cargan lazy via la JVM dentro
 * de los metodos cuando ya verificamos que la dependencia existe.
 */
public final class PacketEventsBootstrap {

    private final ArgusPlugin plugin;
    private boolean available = false;
    private boolean initialized = false;
    private PacketAnticheatListener listener;
    private PacketDataStore dataStore;

    public PacketEventsBootstrap(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /** Detecta si el plugin PacketEvents esta cargado en el server. */
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
            // Verificamos via reflection que la clase API existe (por si la version es muy vieja).
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

    /**
     * Inicializa PacketEvents API y registra el {@link PacketAnticheatListener}.
     * Solo se llama si {@link #detect()} devolvio true. Idempotente.
     */
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
            this.listener  = new PacketAnticheatListener(plugin, dataStore);

            // Imports duros via clase auxiliar — mismo classloader que PacketEvents.
            PacketEventsRegistrar.register(listener);

            // Listener Bukkit auxiliar (join/quit/velocity assignments).
            Bukkit.getPluginManager().registerEvents(
                new PacketAnticheatBukkitBridge(plugin, dataStore, listener), plugin);

            initialized = true;
            plugin.getLogger().info("[Argus/Packet] 10 checks packet-based activos: timer, phase, velocity, "
                + "invalid_rotation, reach_packet, killaura_swing_packet, aim_snap_packet, "
                + "ping_spoof, cps_packet, inv_move_packet");
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
                // best-effort
            }
        }
        initialized = false;
    }

    public boolean isAvailable()      { return available; }
    public boolean isInitialized()    { return initialized; }
    public PacketDataStore getDataStore() { return dataStore; }
}
