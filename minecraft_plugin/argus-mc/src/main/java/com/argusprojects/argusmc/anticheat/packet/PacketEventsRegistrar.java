package com.argusprojects.argusmc.anticheat.packet;

import com.github.retrooper.packetevents.PacketEvents;
import com.github.retrooper.packetevents.event.PacketListenerCommon;

/**
 * Pack 47 — Registrar concreto con imports directos a PacketEvents.
 *
 * <p>El {@link PacketEventsBootstrap} verifica primero si la dependencia esta
 * instalada (via Bukkit#getPluginManager().getPlugin("packetevents")). Solo
 * si esa check pasa, instancia ESTA clase. La idea: si PacketEvents NO esta
 * instalado, esta clase NUNCA se carga y la JVM no falla con NoClassDefFoundError
 * por los imports de arriba.
 *
 * <p>Tener una clase separada con imports duros (en vez de toda la logica
 * en {@code PacketEventsBootstrap} via reflection) tiene dos beneficios:
 * <ol>
 *   <li>Codigo limpio (no reflection).</li>
 *   <li>Usa el mismo classloader que PacketEvents (no hay desync de Class
 *       objects entre classloaders, que era el bug original).</li>
 * </ol>
 */
final class PacketEventsRegistrar {

    static void register(PacketAnticheatListener listener) {
        // SimplePacketListenerAbstract extiende PacketListenerCommon.
        // La priority ya viene seteada desde el constructor del listener.
        PacketListenerCommon plc = listener;
        PacketEvents.getAPI()
            .getEventManager()
            .registerListener(plc);
    }

    static void unregister(PacketAnticheatListener listener) {
        PacketListenerCommon plc = listener;
        PacketEvents.getAPI()
            .getEventManager()
            .unregisterListener(plc);
    }

    /** Verifica que PacketEvents.getAPI() devuelva no-null (init terminado). */
    static boolean isApiReady() {
        try {
            return PacketEvents.getAPI() != null;
        } catch (Throwable t) {
            return false;
        }
    }
}
