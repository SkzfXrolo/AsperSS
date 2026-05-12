-- scripts/db/bench/insert-throughput.sql · Pack 48-H #128
-- INSERT throughput benchmark for Argus core tables.
-- Run against a NON-PROD DB. Targets: localhost dev or ephemeral testcontainer.
--
-- Usage:
--   psql -v rows=10000 -v batch=500 -v table=scans -f insert-throughput.sql
--
-- Env vars (psql -v): rows (default 10000), batch (default 500), table.
--
-- Output:
--   bench_runs row con: tabla, rows, batch_size, total_seconds, rps.

\set rows :rows
\set batch :batch
\set table :'table'

\timing on

CREATE TABLE IF NOT EXISTS bench_runs (
    id            SERIAL PRIMARY KEY,
    run_id        UUID DEFAULT gen_random_uuid(),
    test_name     TEXT NOT NULL,
    target_table  TEXT,
    rows_inserted BIGINT,
    batch_size    INTEGER,
    duration_ms   BIGINT,
    rps           DOUBLE PRECISION,
    notes         TEXT,
    started_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Scenario A · plain INSERT, row by row
DO $$
DECLARE
    i       INT := 0;
    target  INT := :rows;
    started TIMESTAMPTZ := clock_timestamp();
    finished TIMESTAMPTZ;
    dur_ms  BIGINT;
BEGIN
    CREATE TEMP TABLE bench_target_a (id BIGSERIAL, val TEXT, score INT, created_at TIMESTAMPTZ DEFAULT NOW()) ON COMMIT DROP;
    WHILE i < target LOOP
        INSERT INTO bench_target_a (val, score) VALUES (md5(i::text), (random()*100)::int);
        i := i + 1;
    END LOOP;
    finished := clock_timestamp();
    dur_ms := EXTRACT(EPOCH FROM finished - started) * 1000;
    INSERT INTO bench_runs (test_name, target_table, rows_inserted, batch_size, duration_ms, rps, notes)
    VALUES ('insert_row_by_row', 'bench_target_a', target, 1, dur_ms, target*1000.0/NULLIF(dur_ms,0), 'plain INSERT');
END$$;

-- Scenario B · multi-row INSERT (VALUES list)
DO $$
DECLARE
    i       INT := 0;
    target  INT := :rows;
    batch   INT := :batch;
    started TIMESTAMPTZ := clock_timestamp();
    finished TIMESTAMPTZ;
    dur_ms  BIGINT;
BEGIN
    CREATE TEMP TABLE bench_target_b (id BIGSERIAL, val TEXT, score INT, created_at TIMESTAMPTZ DEFAULT NOW()) ON COMMIT DROP;
    WHILE i < target LOOP
        INSERT INTO bench_target_b (val, score)
        SELECT md5((i+g)::text), (random()*100)::int FROM generate_series(0, LEAST(batch, target-i)-1) g;
        i := i + batch;
    END LOOP;
    finished := clock_timestamp();
    dur_ms := EXTRACT(EPOCH FROM finished - started) * 1000;
    INSERT INTO bench_runs (test_name, target_table, rows_inserted, batch_size, duration_ms, rps, notes)
    VALUES ('insert_multi_row', 'bench_target_b', target, batch, dur_ms, target*1000.0/NULLIF(dur_ms,0), 'multi-row VALUES');
END$$;

-- Scenario C · COPY (csv stream simulado por generate_series)
DO $$
DECLARE
    target  INT := :rows;
    started TIMESTAMPTZ := clock_timestamp();
    finished TIMESTAMPTZ;
    dur_ms  BIGINT;
BEGIN
    CREATE TEMP TABLE bench_target_c (id BIGSERIAL, val TEXT, score INT, created_at TIMESTAMPTZ DEFAULT NOW()) ON COMMIT DROP;
    INSERT INTO bench_target_c (val, score)
    SELECT md5(g::text), (random()*100)::int FROM generate_series(1, target) g;
    finished := clock_timestamp();
    dur_ms := EXTRACT(EPOCH FROM finished - started) * 1000;
    INSERT INTO bench_runs (test_name, target_table, rows_inserted, batch_size, duration_ms, rps, notes)
    VALUES ('insert_select_generate', 'bench_target_c', target, target, dur_ms, target*1000.0/NULLIF(dur_ms,0), 'INSERT...SELECT generate_series');
END$$;

-- Scenario D · UPSERT (ON CONFLICT)
DO $$
DECLARE
    target  INT := LEAST(:rows, 5000);
    started TIMESTAMPTZ := clock_timestamp();
    finished TIMESTAMPTZ;
    dur_ms  BIGINT;
BEGIN
    CREATE TEMP TABLE bench_target_d (id BIGINT PRIMARY KEY, val TEXT, hits INT DEFAULT 1) ON COMMIT DROP;
    -- pre-seed
    INSERT INTO bench_target_d (id, val) SELECT g, md5(g::text) FROM generate_series(1, target/2) g;
    -- upsert mix (50% conflict, 50% new)
    INSERT INTO bench_target_d (id, val)
    SELECT g, md5(g::text) FROM generate_series(1, target) g
    ON CONFLICT (id) DO UPDATE SET hits = bench_target_d.hits + 1, val = EXCLUDED.val;
    finished := clock_timestamp();
    dur_ms := EXTRACT(EPOCH FROM finished - started) * 1000;
    INSERT INTO bench_runs (test_name, target_table, rows_inserted, batch_size, duration_ms, rps, notes)
    VALUES ('upsert_on_conflict', 'bench_target_d', target, target, dur_ms, target*1000.0/NULLIF(dur_ms,0), '~50% conflict ratio');
END$$;

-- Reporte
SELECT test_name, rows_inserted, batch_size, duration_ms, round(rps::numeric, 1) AS rps
FROM bench_runs
WHERE started_at >= NOW() - INTERVAL '1 hour'
ORDER BY id DESC
LIMIT 20;
