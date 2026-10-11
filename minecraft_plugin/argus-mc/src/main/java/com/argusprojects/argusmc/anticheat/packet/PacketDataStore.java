package com.argusprojects.argusmc.anticheat.packet;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

public final class PacketDataStore {

    public static final int MOVE_BUFFER_SIZE     = 40;
    public static final int SWING_BUFFER_SIZE    = 128;
    public static final int ATTACK_BUFFER_SIZE   = 64;
    public static final int PLACE_BUFFER_SIZE    = 30;
    public static final int BREAK_BUFFER_SIZE    = 30;
    public static final int ROTATION_BUFFER_SIZE = 20;
    public static final int CHAT_BUFFER_SIZE     = 12;

    public static final class RotationSample {
        public final float yaw;
        public final float pitch;
        public final long  tsMs;
        public RotationSample(float yaw, float pitch, long tsMs) {
            this.yaw = yaw; this.pitch = pitch; this.tsMs = tsMs;
        }
    }

    public static final class ChatSample {
        public final String message;
        public final long   tsMs;
        public ChatSample(String message, long tsMs) {
            this.message = message; this.tsMs = tsMs;
        }
    }

    public static final class State {
        public volatile double lastX, lastY, lastZ;
        public volatile float  lastYaw, lastPitch;
        public volatile boolean rotationResyncPending;
        public volatile org.bukkit.entity.Entity pendingSwingTarget;
        public volatile long   pendingAttackMs;
        public volatile double lastHorizMove;
        public volatile float  prevYaw, prevPitch;
        public volatile int    scaffoldAimConsec;
        public volatile int    groundSpoofConsec;
        public volatile int    noSlowDownConsec;
        public volatile long   noSlowDownLastMs, noSlowSneakLastMs;
        public volatile long   noSlowSneakWinStartMs, lastGroundMoveMs;
        public volatile double noSlowSneakWinDist;
        public volatile boolean packetSneaking;
        public volatile long   sneakToggleMs;
        public volatile double safeWalkDirX, safeWalkDirZ;
        public volatile long   safeWalkPeakMs, safeWalkWindowStartMs;
        public volatile int    safeWalkStops;
        public volatile long   scaffoldSnapMs, scaffoldBelowPlaceMs, scaffoldSnapLastHitMs, scaffoldSnapWindowStartMs;
        public volatile int    scaffoldSnapHits;
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
        public volatile double lastDamageHealthAfter;

        public volatile boolean inventoryOpen;
        public volatile long    inventoryOpenSinceMs;

        public volatile boolean teleporting;
        public volatile long    teleportUntilMs;

        public volatile double lastDeltaY;
        public volatile long   lastOnGroundMs;
        public volatile boolean lastOnGround;

        public volatile int    speedOverflowCounter;
        public volatile long   lastSpeedFlagMs;
        /** Ventana de 1s de desplazamiento horizontal: {tiempoMs, distancia}. Solo lo toca el hilo netty del jugador. */
        public final java.util.ArrayDeque<double[]> speedWindow = new java.util.ArrayDeque<>();
        public volatile long   speedWindowStartMs, speedExemptMs, lastSpeedAvgFlagMs;
        public volatile long   lastTimerFlagMs;
        public volatile long   lastCpsFlagMs;
        public volatile long   lastAutoclickFlagMs;
        public volatile int    pingSpoofLowRttStreak;

        public final Deque<Long> moveTimestamps = new ArrayDeque<>();

        public final Deque<Long> attackTimestamps = new ArrayDeque<>();

        public final Deque<Long> swingTimestamps = new ArrayDeque<>();

        public final Deque<Long> placeTimestamps = new ArrayDeque<>();

        public final Deque<Long> breakTimestamps = new ArrayDeque<>();

        public volatile long currentBreakStartMs;
        public volatile String currentBreakBlockMaterial;

        public final Deque<RotationSample> recentRotations = new ArrayDeque<>();

        public final Deque<ChatSample> recentChat = new ArrayDeque<>();

        public volatile long   boatAirSinceMs;
        public volatile double boatAirStartY;

        public volatile int    jetpackConsec;

        public volatile int    spiderConsec;
        // inventory_macro
        public final long[]    invClickTimes = new long[com.argusprojects.argusmc.anticheat.packet.checks.InventoryMacroCheck.RING];
        public volatile int    invClickCount, invFastOpenHits, invMacroHits;
        public volatile boolean invFirstClickPending;
        public volatile long   invFastOpenWindowMs, lastInvMacroFlagMs, invMacroWindowMs;
        // autosoup
        public volatile long   lastSlotChangeMs, soupUseMs, soupWindowStartMs;
        public volatile int    soupHits;
        // omnisprint
        public volatile boolean packetSprinting;
        public volatile int    omniConsec;
        // triggerbot
        public volatile boolean trigOnTarget, trigArmed;
        public volatile long   trigEnterTick, trigPendingAttackTick = -1, trigLastAttackMs;
        public final int[]     trigReactions = new int[com.argusprojects.argusmc.anticheat.packet.checks.TriggerBotCheck.REACTIONS];
        public volatile int    trigReactionCount, trigSwings, trigAttacks, trigFlags;
        // aim_gcd
        public volatile double gcdLastDelta;
        public volatile int    gcdSamples, gcdNonMouse, gcdLearnCount;
        public volatile double gcdSensEstimate;
        public final java.util.ArrayDeque<Double> gcdCandidates = new java.util.ArrayDeque<>();
        public volatile int    selectedSlot = -1;
        public volatile long   lastRealMoveMs;
        /** Paquetes de movimiento recibidos = ticks del cliente (1.8 manda uno por tick siempre). */
        public volatile long   clientTicks;
        public volatile long   lastPlaceMs;
        public volatile long   nukerFovWindowStartMs;
        public volatile int    nukerFovHits;
        /** Golpe pendiente de evaluar FOV hasta la rotacion siguiente. */
        public volatile org.bukkit.entity.Entity fovTarget;
        public volatile float  fovYaw0, fovPitch0;
        public volatile long   fovAtMs;
        public volatile double fovLag;
        public volatile long   airPlaceWindowStartMs, afkLastFlagMs;
        public volatile int    airPlaceHits, afkRotConsec, afkJumpCount;
        public volatile double afkLastDYaw, afkLastDPitch;
        public final long[]    afkJumps = new long[6];
        public final long[]    swingTicks = new long[com.argusprojects.argusmc.anticheat.packet.checks.AutoClickTickCheck.RING];
        public final long[]    swingTimes = new long[com.argusprojects.argusmc.anticheat.packet.checks.AutoClickTickCheck.RING];
        public volatile int    swingTickCount;
        public volatile long   lastSwingTickMs, lastDigMs, lastAutoClickTickFlagMs;
        public final java.util.ArrayDeque<Long> bowShots = new java.util.ArrayDeque<>();
        public volatile boolean kbPending;
        public volatile double kbX, kbY, kbZ, kbBestAlong, kbBestDy;
        public volatile long   kbAtMs, antiKbWindowStartMs;
        public volatile long   critHopMs, critWindowStartMs;
        public volatile int    critHits;
        public volatile long   lastFastPlaceRhythmFlagMs;
        public volatile double strafePrevDx, strafePrevDz;
        public volatile int    strafeAirTicks, strafeHits;
        public volatile long   strafeWindowStartMs;
        public volatile long   spiderWindowStartMs;

        public volatile int    velocityIgnoredConsec;

        public volatile int    liquidWalkConsec;

        public volatile int    meleeFlyConsec;

        public volatile long   lastBowChargeStartMs;

        public volatile String lastMainHandItemName;
        public volatile long   lastMainHandItemNameMs;

        public volatile int    namedChangesInWindow;

        public volatile double trustScore = 50.0;

        public volatile UUID   watchedBy;

        public volatile long   useItemStartMs;

        public volatile String useItemMaterial;

        public volatile long   lastEatFinishMs;

        public volatile long   lastBowChargeMs;

        public volatile boolean sneakActive;
        public volatile long    sneakStartMs;

        public volatile long    lastArmorChangeMs;

        public volatile double  lastHealth = 20.0;
        public volatile long    lastHealthChangeMs;

        public volatile int     regenAnomaliesInWindow;

        public volatile String  clientBrand;

        public volatile int     cancelledViolations;

        public volatile long    lastKnockbackExpectedMs;

        public volatile double  lastKnockbackExpectedMag;

        public volatile int     autoEatPatternHits;
        public volatile long    autoEatLastEventMs;

        public volatile int     noSwingConsec;
        public volatile int     thruWallConsec;
        public volatile int     scaffoldRotConsec;
        public volatile int     scaffoldTowerConsec;
        public volatile int     lastTowerX, lastTowerZ;
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
        public synchronized int recentSwingsWithin(long windowMs, long now) {
            int n = 0;
            for (Long t : swingTimestamps) if (now - t <= windowMs) n++;
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
            lastSpeedFlagMs = 0L;
            lastTimerFlagMs = 0L;
            lastCpsFlagMs = 0L;
            lastAutoclickFlagMs = 0L;
            pingSpoofLowRttStreak = 0;
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

    public java.util.Set<UUID> keys() {
        return new java.util.HashSet<>(states.keySet());
    }
}
