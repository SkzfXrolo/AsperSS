package com.argusprojects.argusmc.anticheat.packet;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Pack 47 — Estado per-player para checks packet-based.
 *
 * <p>Mantiene una imagen ligera del jugador desde la perspectiva de los packets
 * crudos: ultimas posiciones, ultimas rotaciones, RTT de KeepAlive, asignaciones
 * de velocity del server (para diff vs movimiento real del cliente), timestamps
 * de los ultimos N clicks/swings, y la cola de packets de movimiento usada por
 * TimerCheck.
 *
 * <p>Thread-safe. Cada metodo de mutacion sincroniza solo lo necesario para
 * minimizar contencion (los listeners de packets corren en el thread de Netty,
 * no en el main thread de Bukkit).
 */
public final class PacketDataStore {

    /** Estado completo por jugador. Una sola entrada vive en este map. */
    public static final class State {
        public volatile double lastX, lastY, lastZ;
        public volatile float  lastYaw, lastPitch;
        public volatile long   lastMoveMs;
        public volatile long   joinMs;

        public volatile double serverVelX, serverVelY, serverVelZ;
        public volatile long   serverVelAssignedAtMs;
        public volatile boolean serverVelConsumed;

        public volatile long lastKeepAliveSentMs;
        public volatile long lastKeepAliveRecvMs;
        public volatile long pingMs = 50L;

        public volatile long lastSwingMs;
        public volatile long lastAttackMs;
        public volatile long lastClickWindowMs;

        public volatile boolean inventoryOpen;
        public volatile long    inventoryOpenSinceMs;

        public volatile boolean teleporting;
        public volatile long    teleportUntilMs;

        /** Timestamps de los ultimos PlayerPosition packets (TimerCheck) — bounded a 40. */
        public final Deque<Long> moveTimestamps = new ArrayDeque<>();
        /** Timestamps de los ultimos clicks de combate (CPSPacketCheck) — bounded a 20. */
        public final Deque<Long> attackTimestamps = new ArrayDeque<>();
        /** Timestamps de los ultimos swings (KillauraSwingPacketCheck) — bounded a 20. */
        public final Deque<Long> swingTimestamps = new ArrayDeque<>();

        public synchronized void pushMove(long now) {
            moveTimestamps.addLast(now);
            while (moveTimestamps.size() > 40) moveTimestamps.pollFirst();
        }
        public synchronized void pushAttack(long now) {
            attackTimestamps.addLast(now);
            while (attackTimestamps.size() > 20) attackTimestamps.pollFirst();
        }
        public synchronized void pushSwing(long now) {
            swingTimestamps.addLast(now);
            while (swingTimestamps.size() > 20) swingTimestamps.pollFirst();
        }

        public synchronized int recentAttacksWithin(long windowMs, long now) {
            int n = 0;
            for (Long t : attackTimestamps) if (now - t <= windowMs) n++;
            return n;
        }
    }

    private final Map<UUID, State> states = new ConcurrentHashMap<>();

    public State get(UUID uuid) {
        return states.computeIfAbsent(uuid, k -> {
            State s = new State();
            s.joinMs = System.currentTimeMillis();
            return s;
        });
    }

    public State peek(UUID uuid) {
        return states.get(uuid);
    }

    public void remove(UUID uuid) {
        states.remove(uuid);
    }

    public int size() {
        return states.size();
    }
}
