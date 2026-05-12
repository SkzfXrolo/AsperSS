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
    public static final int MOVE_BUFFER_SIZE     = 40;
    public static final int ATTACK_BUFFER_SIZE   = 20;
    public static final int SWING_BUFFER_SIZE    = 20;
    public static final int PLACE_BUFFER_SIZE    = 30;
    public static final int BREAK_BUFFER_SIZE    = 30;
    public static final int ROTATION_BUFFER_SIZE = 20;
    public static final int CHAT_BUFFER_SIZE     = 12;

    /** Sample de rotacion (yaw/pitch) capturado con timestamp para checks de aim. */
    public static final class RotationSample {
        public final float yaw;
        public final float pitch;
        public final long  tsMs;
        public RotationSample(float yaw, float pitch, long tsMs) {
            this.yaw = yaw; this.pitch = pitch; this.tsMs = tsMs;
        }
    }

    /** Sample de chat (texto + timestamp) para ChatMacroCheck. */
    public static final class ChatSample {
        public final String message;
        public final long   tsMs;
        public ChatSample(String message, long tsMs) {
            this.message = message; this.tsMs = tsMs;
        }
    }

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
        /** Contador de packets consecutivos por encima del cap de speed (SpeedPacketCheck). */
        public volatile int    speedOverflowCounter;

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

        // ===== round 2 (Pack 48-A) =====

        /** Buffer de rotaciones recientes (KillauraAimCheck / BowAimCheck). */
        public final Deque<RotationSample> recentRotations = new ArrayDeque<>();
        /** Buffer de mensajes de chat recientes (ChatMacroCheck). */
        public final Deque<ChatSample> recentChat = new ArrayDeque<>();

        /** BoatFly state — desde cuando el boat lleva en aire sin tocar agua / suelo. */
        public volatile long   boatAirSinceMs;
        public volatile double boatAirStartY;
        /** Jetpack consec counter — packets seguidos con dy positivo grande. */
        public volatile int    jetpackConsec;
        /** Spider consec counter — packets seguidos subiendo pegado a pared. */
        public volatile int    spiderConsec;
        /** Multi-velocity ignored counter — packets seguidos en los que el cliente ignoro velocity. */
        public volatile int    velocityIgnoredConsec;
        /** Liquid walk consec counter — packets seguidos caminando sobre liquido. */
        public volatile int    liquidWalkConsec;
        /** MeleeFly hover counter — attacks seguidos en aire/no fall. */
        public volatile int    meleeFlyConsec;
        /** Ultimo ts de bow charge start (release event clave). */
        public volatile long   lastBowChargeStartMs;
        /** Ultimo nombre custom de item visto en main hand (NamedItemSpamCheck). */
        public volatile String lastMainHandItemName;
        public volatile long   lastMainHandItemNameMs;
        /** Contador de renames dentro de la ventana NamedItemSpamCheck. */
        public volatile int    namedChangesInWindow;
        /** Trust score Argus (0-100). Se actualiza on backend response — defualt 50. */
        public volatile double trustScore = 50.0;
        /** Verbose watcher (UUID del admin observando) — null si nadie observa. */
        public volatile UUID   watchedBy;

        // ===== round 3 (Pack 48-A) =====

        /** Cuando empezo el use-item action (eat/bow/shield) — 0 si nada. */
        public volatile long   useItemStartMs;
        /** Material del item en uso (formato Material.name()). */
        public volatile String useItemMaterial;
        /** Cuando termino el ultimo eat completo. */
        public volatile long   lastEatFinishMs;
        /** Charge time del ultimo bow shot completado. */
        public volatile long   lastBowChargeMs;
        /** Velocidad horizontal mientras "sneaking" — para NoSlowSneak. */
        public volatile boolean sneakActive;
        public volatile long    sneakStartMs;
        /** Ultima vez que cambio armor el jugador (in-combat o no). */
        public volatile long    lastArmorChangeMs;
        /** Health en el ultimo HealthChangeEvent observado — para Regen. */
        public volatile double  lastHealth = 20.0;
        public volatile long    lastHealthChangeMs;
        /** Counter de regen events anomalos dentro de la ventana. */
        public volatile int     regenAnomaliesInWindow;
        /** Brand del cliente (Lunar/Vanilla/Forge/Optifine) — LegitClientWhitelist. */
        public volatile String  clientBrand;
        /** Contador de FPs detectados/canceled (FalsePositiveLogger). */
        public volatile int     cancelledViolations;
        /** Cuando recibio el ultimo daño con KB esperado del server (AntiKnockback). */
        public volatile long    lastKnockbackExpectedMs;
        /** Magnitud del KB esperado (sqrt(vx²+vz²)) que el cliente debería absorber. */
        public volatile double  lastKnockbackExpectedMag;
        /** Hit-pattern reciente: secuencia de attacks alternados con eat (AutoEat). */
        public volatile int     autoEatPatternHits;
        public volatile long    autoEatLastEventMs;
        /** Counters dedicados a checks de Round 3. */
        public volatile int     noSwingConsec;
        public volatile int     thruWallConsec;
        public volatile int     scaffoldRotConsec;
        public volatile int     scaffoldTowerConsec;
        public volatile long    lastScaffoldPlaceMs;
        public volatile int     lastScaffoldPlaceY;
        public volatile int     phaseConsec;
        public volatile int     antiKbConsec;
        public volatile int     noSlowSneakConsec;
        public volatile int     liquidJesusConsec;
        public volatile int     reach3dConsec;
        public volatile int     aimbotConsec;
        public volatile int     tracersConsec;

        public synchronized void pushRotation(float yaw, float pitch, long now) {
            recentRotations.addLast(new RotationSample(yaw, pitch, now));
            while (recentRotations.size() > ROTATION_BUFFER_SIZE) recentRotations.pollFirst();
        }
        public synchronized void pushChat(String msg, long now) {
            recentChat.addLast(new ChatSample(msg, now));
            while (recentChat.size() > CHAT_BUFFER_SIZE) recentChat.pollFirst();
        }

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
            recentRotations.clear();
            recentChat.clear();
            serverVelConsumed = true;
            currentBreakStartMs = 0L;
            currentBreakBlockMaterial = null;
            speedOverflowCounter = 0;
            boatAirSinceMs = 0L;
            boatAirStartY  = 0.0;
            jetpackConsec = 0;
            spiderConsec  = 0;
            velocityIgnoredConsec = 0;
            liquidWalkConsec = 0;
            meleeFlyConsec   = 0;
            lastBowChargeStartMs = 0L;
            lastMainHandItemName = null;
            lastMainHandItemNameMs = 0L;
            namedChangesInWindow = 0;
            useItemStartMs = 0L;
            useItemMaterial = null;
            lastEatFinishMs = 0L;
            lastBowChargeMs = 0L;
            sneakActive = false;
            sneakStartMs = 0L;
            lastArmorChangeMs = 0L;
            regenAnomaliesInWindow = 0;
            lastKnockbackExpectedMs = 0L;
            lastKnockbackExpectedMag = 0.0;
            autoEatPatternHits = 0;
            autoEatLastEventMs = 0L;
            noSwingConsec = 0;
            thruWallConsec = 0;
            scaffoldRotConsec = 0;
            scaffoldTowerConsec = 0;
            lastScaffoldPlaceMs = 0L;
            lastScaffoldPlaceY = 0;
            phaseConsec = 0;
            antiKbConsec = 0;
            noSlowSneakConsec = 0;
            liquidJesusConsec = 0;
            reach3dConsec = 0;
            aimbotConsec = 0;
            tracersConsec = 0;
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
