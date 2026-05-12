package com.argusprojects.argusmc.api;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;

import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Pack 48 round 2 — Buffer asincrono para envio de violations al backend.
 *
 * <p>Reduce GC pressure y latencia: en lugar de hacer un HTTP/sec por cada
 * violation, las acumula en una cola lock-free y un worker scheduler
 * dispara batches cada {@link #FLUSH_INTERVAL_SEC} segundos.
 *
 * <p>Si el buffer crece por encima del cap, descarta los mas viejos
 * (back-pressure / leak protection). Estadisticas accesibles para
 * {@code /argus admin stats} y bStats.
 */
public final class ViolationBuffer {

    private static final int  CAP                = 1_000;
    private static final long FLUSH_INTERVAL_SEC = 5L;
    private static final int  MAX_BATCH_PER_TICK = 50;

    private final ArgusPlugin plugin;
    private final ArgusApiClient apiClient;
    private final ConcurrentLinkedQueue<Violation> queue = new ConcurrentLinkedQueue<>();
    private final AtomicLong queued    = new AtomicLong();
    private final AtomicLong sent      = new AtomicLong();
    private final AtomicLong dropped   = new AtomicLong();
    private final ScheduledExecutorService worker;

    public ViolationBuffer(ArgusPlugin plugin, ArgusApiClient apiClient) {
        this.plugin = plugin;
        this.apiClient = apiClient;
        this.worker = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "ArgusMC-ViolationBuffer");
            t.setDaemon(true);
            return t;
        });
        worker.scheduleAtFixedRate(this::flush, FLUSH_INTERVAL_SEC, FLUSH_INTERVAL_SEC, TimeUnit.SECONDS);
    }

    /** Encola una violation; descarta la mas vieja si el buffer esta lleno. */
    public void offer(Violation v) {
        if (v == null) return;
        queue.offer(v);
        if (queued.incrementAndGet() > CAP) {
            Violation drop = queue.poll();
            if (drop != null) {
                queued.decrementAndGet();
                dropped.incrementAndGet();
            }
        }
    }

    /** Drena hasta {@link #MAX_BATCH_PER_TICK} violations y dispara HTTP por cada una. */
    private void flush() {
        int processed = 0;
        Violation v;
        while (processed < MAX_BATCH_PER_TICK && (v = queue.poll()) != null) {
            queued.decrementAndGet();
            try {
                apiClient.reportViolationAsync(v);
                sent.incrementAndGet();
            } catch (Throwable t) {
                plugin.getLogger().fine(() ->
                    "[ArgusBuffer] flush err: " + t.getClass().getSimpleName());
            }
            processed++;
        }
    }

    /** Estadisticas para /argus admin stats. */
    public long queueSize() { return queued.get(); }
    public long sentTotal() { return sent.get(); }
    public long droppedTotal() { return dropped.get(); }

    /** Shutdown en onDisable(). */
    public void shutdown() {
        try {
            flush();
            worker.shutdown();
            worker.awaitTermination(2, TimeUnit.SECONDS);
        } catch (Throwable ignored) {
        }
    }
}
