package com.argusprojects.argusmc.anticheat.packet;

import org.junit.jupiter.api.Test;

import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Pack 48 round 2 — unit tests para {@link PacketDataStore}.
 *
 * <p>Cubre los aspectos sin Bukkit: bounded collections, thread-safety,
 * clearTransient() y lifecycle del map UUID -> State.
 */
class PacketDataStoreTest {

    @Test
    void getOrCreateReturnsSameInstancePerUuid() {
        PacketDataStore store = new PacketDataStore();
        UUID u = UUID.randomUUID();
        PacketDataStore.State a = store.get(u);
        PacketDataStore.State b = store.get(u);
        assertSame(a, b, "el mismo UUID debe devolver el mismo State");
    }

    @Test
    void peekReturnsNullBeforeFirstGet() {
        PacketDataStore store = new PacketDataStore();
        assertNull(store.peek(UUID.randomUUID()));
    }

    @Test
    void removeClearsState() {
        PacketDataStore store = new PacketDataStore();
        UUID u = UUID.randomUUID();
        store.get(u);
        assertEquals(1, store.size());
        store.remove(u);
        assertEquals(0, store.size());
        assertNull(store.peek(u));
    }

    @Test
    void moveBufferIsBoundedAt40() {
        PacketDataStore.State s = new PacketDataStore.State();
        for (int i = 0; i < 100; i++) s.pushMove(i);
        assertEquals(PacketDataStore.MOVE_BUFFER_SIZE, s.moveTimestamps.size());
        assertEquals(60L, s.moveTimestamps.peekFirst());
        assertEquals(99L, s.moveTimestamps.peekLast());
    }

    @Test
    void attackBufferIsBoundedAt20() {
        PacketDataStore.State s = new PacketDataStore.State();
        for (int i = 0; i < 100; i++) s.pushAttack(i);
        assertEquals(PacketDataStore.ATTACK_BUFFER_SIZE, s.attackTimestamps.size());
    }

    @Test
    void swingBufferIsBoundedAt20() {
        PacketDataStore.State s = new PacketDataStore.State();
        for (int i = 0; i < 100; i++) s.pushSwing(i);
        assertEquals(PacketDataStore.SWING_BUFFER_SIZE, s.swingTimestamps.size());
    }

    @Test
    void placeBufferIsBoundedAt30() {
        PacketDataStore.State s = new PacketDataStore.State();
        for (int i = 0; i < 100; i++) s.pushPlace(i);
        assertEquals(PacketDataStore.PLACE_BUFFER_SIZE, s.placeTimestamps.size());
    }

    @Test
    void breakBufferIsBoundedAt30() {
        PacketDataStore.State s = new PacketDataStore.State();
        for (int i = 0; i < 100; i++) s.pushBreak(i);
        assertEquals(PacketDataStore.BREAK_BUFFER_SIZE, s.breakTimestamps.size());
    }

    @Test
    void rotationBufferIsBoundedAt20() {
        PacketDataStore.State s = new PacketDataStore.State();
        for (int i = 0; i < 100; i++) s.pushRotation(i, i * 0.5f, i);
        assertEquals(PacketDataStore.ROTATION_BUFFER_SIZE, s.recentRotations.size());
    }

    @Test
    void chatBufferIsBoundedAt12() {
        PacketDataStore.State s = new PacketDataStore.State();
        for (int i = 0; i < 100; i++) s.pushChat("msg" + i, i);
        assertEquals(PacketDataStore.CHAT_BUFFER_SIZE, s.recentChat.size());
    }

    @Test
    void recentAttacksWithinReturnsOnlyRecent() {
        PacketDataStore.State s = new PacketDataStore.State();
        long now = 10_000L;
        s.pushAttack(now - 100);
        s.pushAttack(now - 500);
        s.pushAttack(now - 2_000); // fuera
        s.pushAttack(now - 50);
        int recent = s.recentAttacksWithin(1_000L, now);
        assertEquals(3, recent);
    }

    @Test
    void recentPlacesWithinReturnsZeroForEmpty() {
        PacketDataStore.State s = new PacketDataStore.State();
        assertEquals(0, s.recentPlacesWithin(1_000L, System.currentTimeMillis()));
    }

    @Test
    void clearTransientResetsAllBuffers() {
        PacketDataStore.State s = new PacketDataStore.State();
        s.pushMove(1L);
        s.pushAttack(2L);
        s.pushSwing(3L);
        s.pushPlace(4L);
        s.pushBreak(5L);
        s.pushRotation(0f, 0f, 6L);
        s.pushChat("x", 7L);
        s.jetpackConsec = 5;
        s.spiderConsec  = 5;
        s.boatAirSinceMs = 1L;
        s.liquidWalkConsec = 7;
        s.meleeFlyConsec   = 9;
        s.lastMainHandItemName = "abc";
        s.lastBowChargeStartMs = 100L;

        s.clearTransient();

        assertTrue(s.moveTimestamps.isEmpty());
        assertTrue(s.attackTimestamps.isEmpty());
        assertTrue(s.swingTimestamps.isEmpty());
        assertTrue(s.placeTimestamps.isEmpty());
        assertTrue(s.breakTimestamps.isEmpty());
        assertTrue(s.recentRotations.isEmpty());
        assertTrue(s.recentChat.isEmpty());
        assertEquals(0, s.jetpackConsec);
        assertEquals(0, s.spiderConsec);
        assertEquals(0L, s.boatAirSinceMs);
        assertEquals(0, s.liquidWalkConsec);
        assertEquals(0, s.meleeFlyConsec);
        assertEquals(0L, s.lastBowChargeStartMs);
        assertNull(s.lastMainHandItemName);
    }

    @Test
    void concurrentPushesDoNotLoseData() throws InterruptedException {
        PacketDataStore.State s = new PacketDataStore.State();
        ExecutorService pool = Executors.newFixedThreadPool(4);
        AtomicInteger seq = new AtomicInteger();
        for (int t = 0; t < 4; t++) {
            pool.submit(() -> {
                for (int i = 0; i < 1000; i++) {
                    s.pushMove(seq.incrementAndGet());
                }
            });
        }
        pool.shutdown();
        assertTrue(pool.awaitTermination(5, TimeUnit.SECONDS));
        // Tras 4000 pushes, queda exactamente MOVE_BUFFER_SIZE (40)
        // gracias al cap interno.
        assertEquals(PacketDataStore.MOVE_BUFFER_SIZE, s.moveTimestamps.size());
    }

    @Test
    void keysReturnsAllUuids() {
        PacketDataStore store = new PacketDataStore();
        UUID a = UUID.randomUUID();
        UUID b = UUID.randomUUID();
        store.get(a); store.get(b);
        assertEquals(2, store.keys().size());
        assertTrue(store.keys().contains(a));
        assertTrue(store.keys().contains(b));
    }

    @Test
    void initialJoinMsIsPositive() {
        PacketDataStore store = new PacketDataStore();
        long before = System.currentTimeMillis();
        PacketDataStore.State s = store.get(UUID.randomUUID());
        long after = System.currentTimeMillis();
        assertTrue(s.joinMs >= before && s.joinMs <= after);
    }
}
