package com.argusprojects.argusmc.anticheat.packet;

import com.github.retrooper.packetevents.PacketEvents;
import com.github.retrooper.packetevents.event.PacketListenerCommon;

final class PacketEventsRegistrar {

    static void register(PacketAnticheatListener listener) {

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

    static boolean isApiReady() {
        try {
            return PacketEvents.getAPI() != null;
        } catch (Throwable t) {
            return false;
        }
    }
}
