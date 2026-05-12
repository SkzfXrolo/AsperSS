-- scripts/db/bench/concurrent-write.sql · Pack 48-H #128
-- Concurrent write benchmark. This script generates a "session" payload;
-- run multiple psql sessions in parallel (see run-bench.sh) to simulate load.
--
-- Each session:
--   - Crea N inserts en bench_concurrent_target.
--   - Mide latencia individual.
--   - Reporta resultados al final.
--
-- Esperado: ver impact de transactions vs autocommit, locks, deadlocks.
--
-- Usage (single session):
--   psql -v iters=500 -v worker=1 -f concurrent-write.sql

\set iters :iters
\set worker :worker

CREATE TABLE IF NOT EXISTS bench_concurrent_target (
    id           BIGSERIAL PRIMARY KEY,
    worker_id    INT NOT NULL,
    payload      JSONB NOT NULL,
    counter      INT NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bench_ct_worker ON bench_concurrent_target(worker_id, created_at);

CREATE TABLE IF NOT EXISTS bench_concurrent_results (
    id SERIAL PRIMARY KEY, run_id UUID,
    worker_id INT, iter INT, duration_us BIGINT,
    captured_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scenario · mix INSERT + UPDATE on shared row (worst case for locks)
DO $$
DECLARE
    iters INT := :iters;
    worker INT := :worker;
    i INT := 0; rid UUID := gen_random_uuid();
    t0 TIMESTAMPTZ; t1 TIMESTAMPTZ;
    shared_id BIGINT;
BEGIN
    INSERT INTO bench_concurrent_target (worker_id, payload, counter)
    VALUES (0, '{"shared":true}'::jsonb, 0)
    RETURNING id INTO shared_id;

    WHILE i < iters LOOP
        BEGIN
            t0 := clock_timestamp();
            INSERT INTO bench_concurrent_target (worker_id, payload, counter)
            VALUES (worker, jsonb_build_object('i', i, 'rand', random()), i);
            -- contention point: update shared row
            UPDATE bench_concurrent_target SET counter = counter + 1
            WHERE id = shared_id;
            t1 := clock_timestamp();
            INSERT INTO bench_concurrent_results (run_id, worker_id, iter, duration_us)
            VALUES (rid, worker, i, EXTRACT(EPOCH FROM t1-t0)*1000000);
        EXCEPTION WHEN deadlock_detected THEN
            -- retry once
            CONTINUE;
        END;
        i := i + 1;
    END LOOP;
END$$;

SELECT
    worker_id, count(*) AS n,
    round(percentile_disc(0.50) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p50_us,
    round(percentile_disc(0.95) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p95_us,
    round(percentile_disc(0.99) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p99_us,
    max(duration_us) AS max_us
FROM bench_concurrent_results
WHERE captured_at >= NOW() - INTERVAL '10 minutes'
GROUP BY worker_id
ORDER BY worker_id;
