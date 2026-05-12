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
 * <h3>Contrato de thread-safety (audit Pack 48 #481)</h3>
 * <ul>
 *   <li>Las deques con timestamps ({@code moveTimestamps},
 *       {@code attackTimestamps}, {@code swingTimestamps}, plus las nuevas
 *       {@code placeTimestamps}, {@code breakTimestamps},
 *       {@code breakCompletionTimestamps}) <b>siempre</b> se acceden bajo
 *       el monitor de la State (sea via los metodos {@code pushX/recentX}
 *       o via bloque {@code synchronized(state)} explicito en los checks).</li>
 *   <li>Las primitivas individuales son {@code volatile} — lecturas y
 *       escrituras concurrentes desde Netty + main thread son seguras
 *       sin sincronizar (cada campo es un snapshot atomico).</li>
 *   <li>Los deques estan bounded por las constantes
 *       {@link #MOVE_BUFFER_SIZE}/{@link #ATTACK_BUFFER_SIZE}/{@link #SWING_BUFFER_SIZE}/{@link #PLACE_BUFFER_SIZE}/{@link #BREAK_BUFFER_SIZE}
 *       — no pueden crecer sin cota.</li>
 *   <li>La inicializacion lazy en {@link #get(UUID)} es benigna: el
 *       PacketAnticheatBukkitBridge sobreescribe {@code joinMs}/{@code lastX,Y,Z}
 *       en {@code PlayerJoinEvent} (priority MONITOR) antes que cualquier
 *       packet llegue de un cliente recien conectado.</li>
 * </ul>
 */
public final class PacketDataStore {

    /** Tamaños maximos de los buffers circulares por State. */
    public static final int MOVE_BUFFER_SIZE   = 40;
    public static final int ATTACK_BUFFER_SIZE = 20;
    public static final int SWING_BUFFER_SIZE  = 20;
    public static final int PLACE_BUFFER_SIZE  = 30;
    public static final int BREAK_BUFFER_SIZE  = 30;

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
        public volatile long lastDamageTakenMs;
        public volatile double lastDamageHealthAfter; // health post-damage para AutoTotem

        public volatile boolean inventoryOpen;
        public volatile long    inventoryOpenSinceMs;

        public volatile boolean teleporting;
        public volatile long    teleportUntilMs;

        /** Telemetria de movimiento para checks de jump/step/vclip. */
        public volatile double lastDeltaY;
        public volatile long   lastOnGroundMs;
        public volatile boolean lastOnGround;

        /** Timestamps de los ultimos PlayerPosition packets (TimerCheck) — bounded. */
        public final Deque<Long> moveTimestamps = new ArrayDeque<>();
        /** Timestamps de los ultimos clicks de combate (CPSPacketCheck) — bounded. */
        public final Deque<Long> attackTimestamps = new ArrayDeque<>();
        /** Timestamps de los ultimos swings (KillauraSwingPacketCheck) — bounded. */
        public final Deque<Long> swingTimestamps = new ArrayDeque<>();
        /** Timestamps de los ultimos BlockPlacement packets (FastPlace) — bounded. */
        public final Deque<Long> placeTimestamps = new ArrayDeque<>();
        /** Timestamps de los ultimos block break events / completions (FastBreak/Nuker) — bounded. */
        public final Deque<Long> breakTimestamps = new ArrayDeque<>();
        /** Cuando empezo el break en curso (PLAYER_DIGGING START_DIGGING) — 0 si no esta minando. */
        public volatile long currentBreakStartMs;
        public volatile String currentBreakBlockMaterial;

        public synchronized void pushMove(long now) {
            moveTimestamps.addLast(now);
            while (moveTimestamps.size() > MOVE_BUFFER_SIZE) moveTimestamps.pollFirst();
        }
        public synchronized void pushAttack(long now) {
            attackTimestamps.addLast(now);
            while (attackTimestamps.size() > ATTACK_BUFFER_SIZE) attackTimestamps.pollFirst();
        }
        public synchronized void pushSwing(long now) {
            swingTimestamps.addLast(now);
            while (swingTimestamps.size() > SWING_BUFFER_SIZE) swingTimestamps.pollFirst();
        }
        public synchronized void pushPlace(long now) {
            placeTimestamps.addLast(now);
            while (placeTimestamps.size() > PLACE_BUFFER_SIZE) placeTimestamps.pollFirst();
        }
        public synchronized void pushBreak(long now) {
            breakTimestamps.addLast(now);
            while (breakTimestamps.size() > BREAK_BUFFER_SIZE) breakTimestamps.pollFirst();
        }

        public synchronized int recentAttacksWithin(long windowMs, long now) {
            int n = 0;
            for (Long t : attackTimestamps) if (now - t <= windowMs) n++;
            return n;
        }
        public synchronized int recentPlacesWithin(long windowMs, long now) {
            int n = 0;
            for (Long t : placeTimestamps) if (now - t <= windowMs) n++;
            return n;
        }
        public synchronized int recentBreaksWithin(long windowMs, long now) {
            int n = 0;
            for (Long t : breakTimestamps) if (now - t <= windowMs) n++;
            return n;
        }

        /** Limpia todo el estado in-flight (testpacket / clearviolations). */
        public synchronized void clearTransient() {
            moveTimestamps.clear();
            attackTimestamps.clear();
            swingTimestamps.clear();
            placeTimestamps.clear();
            breakTimestamps.clear();
            serverVelConsumed = true;
            currentBreakStartMs = 0L;
            currentBreakBlockMaterial = null;
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

    /** Snapshot del set de UUIDs activos (para debug commands). */
    public java.util.Set<UUID> keys() {
        return new java.util.HashSet<>(states.keySet());
    }
}
