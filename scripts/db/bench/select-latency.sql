-- scripts/db/bench/select-latency.sql · Pack 48-H #128
-- SELECT latency benchmark (p50/p95/p99 by simulating N iterations).
-- Run on NON-PROD DB with realistic seed data (`seed-data.sql` + `synthetic-data-generator.py`).
--
-- Usage:
--   psql -v iters=200 -f select-latency.sql

\set iters :iters
\timing on

CREATE TABLE IF NOT EXISTS bench_runs (
    id SERIAL PRIMARY KEY, run_id UUID DEFAULT gen_random_uuid(),
    test_name TEXT, target_table TEXT, rows_inserted BIGINT,
    batch_size INTEGER, duration_ms BIGINT, rps DOUBLE PRECISION,
    notes TEXT, started_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bench_latencies (
    id SERIAL PRIMARY KEY, run_id UUID,
    test_name TEXT, iter INT, duration_us BIGINT,
    captured_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scenario A · point lookup by primary key (assumes table `scans` exists)
DO $$
DECLARE
    iters INT := :iters;
    i INT := 0; rid UUID := gen_random_uuid(); pk BIGINT;
    t0 TIMESTAMPTZ; t1 TIMESTAMPTZ;
BEGIN
    PERFORM 1 FROM pg_class WHERE relname='scans';
    IF NOT FOUND THEN RAISE NOTICE 'skip A: scans table missing'; RETURN; END IF;
    WHILE i < iters LOOP
        SELECT id INTO pk FROM scans ORDER BY random() LIMIT 1;
        t0 := clock_timestamp();
        PERFORM * FROM scans WHERE id = pk;
        t1 := clock_timestamp();
        INSERT INTO bench_latencies (run_id, test_name, iter, duration_us)
        VALUES (rid, 'select_pk', i, EXTRACT(EPOCH FROM t1-t0)*1000000);
        i := i + 1;
    END LOOP;
END$$;

-- Scenario B · indexed range (last 100 rows by created_at)
DO $$
DECLARE
    iters INT := :iters;
    i INT := 0; rid UUID := gen_random_uuid();
    t0 TIMESTAMPTZ; t1 TIMESTAMPTZ;
BEGIN
    PERFORM 1 FROM pg_class WHERE relname='scans';
    IF NOT FOUND THEN RAISE NOTICE 'skip B: scans table missing'; RETURN; END IF;
    WHILE i < iters LOOP
        t0 := clock_timestamp();
        PERFORM * FROM scans ORDER BY created_at DESC LIMIT 100;
        t1 := clock_timestamp();
        INSERT INTO bench_latencies (run_id, test_name, iter, duration_us)
        VALUES (rid, 'select_recent_100', i, EXTRACT(EPOCH FROM t1-t0)*1000000);
        i := i + 1;
    END LOOP;
END$$;

-- Scenario C · aggregated stats per company (last 24h)
DO $$
DECLARE
    iters INT := :iters;
    i INT := 0; rid UUID := gen_random_uuid();
    t0 TIMESTAMPTZ; t1 TIMESTAMPTZ;
BEGIN
    PERFORM 1 FROM pg_class WHERE relname='scans';
    IF NOT FOUND THEN RAISE NOTICE 'skip C: scans table missing'; RETURN; END IF;
    WHILE i < iters LOOP
        t0 := clock_timestamp();
        PERFORM company_id, count(*), avg(risk_score::numeric)
        FROM scans
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY company_id;
        t1 := clock_timestamp();
        INSERT INTO bench_latencies (run_id, test_name, iter, duration_us)
        VALUES (rid, 'agg_company_24h', i, EXTRACT(EPOCH FROM t1-t0)*1000000);
        i := i + 1;
    END LOOP;
END$$;

-- Report percentiles
SELECT
    test_name,
    count(*) AS n,
    round(percentile_disc(0.50) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p50_us,
    round(percentile_disc(0.95) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p95_us,
    round(percentile_disc(0.99) WITHIN GROUP (ORDER BY duration_us)::numeric, 1) AS p99_us,
    max(duration_us) AS max_us
FROM bench_latencies
WHERE captured_at >= NOW() - INTERVAL '10 minutes'
GROUP BY test_name
ORDER BY test_name;
