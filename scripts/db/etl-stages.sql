-- ============================================================================
-- Argus Projects — Pack 48-H Round 3 · #93
-- etl-stages.sql
-- ----------------------------------------------------------------------------
-- ETL: Raw → Staging → Cleaned → Aggregated. Idempotente.
-- ⚠️  No ejecutar en prod sin staging. Crear primero las MVs (#90).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 0 · Tabla de auditoría de runs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID        NOT NULL DEFAULT gen_random_uuid(),
    stage           TEXT        NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'running',
    rows_in         BIGINT,
    rows_out        BIGINT,
    error_msg       TEXT
);
CREATE INDEX IF NOT EXISTS idx_etl_runs_stage_started
    ON etl_runs (stage, started_at DESC);

-- ---------------------------------------------------------------------------
-- 1 · RAW · vistas 1:1 de tablas OLTP (sin transformación, para auditoría)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW raw_scans AS
SELECT *, NOW() AS _viewed_at FROM scans;

CREATE OR REPLACE VIEW raw_violations AS
SELECT *, NOW() AS _viewed_at FROM plugin_violations;

CREATE OR REPLACE VIEW raw_ai_decisions AS
SELECT *, NOW() AS _viewed_at FROM ai_decisions_log;

-- ---------------------------------------------------------------------------
-- 2 · STAGING · tipos canónicos, claves derivadas
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_scans (
    scan_id             BIGINT       PRIMARY KEY,
    company_id          INTEGER,     -- nullable hasta F-001
    token_id            BIGINT,
    started_at          TIMESTAMPTZ  NOT NULL,
    completed_at        TIMESTAMPTZ,
    status              VARCHAR(32),
    verdict             VARCHAR(32),
    risk_score          NUMERIC(6,2),
    machine_id_text     TEXT,
    player_uuid_canon   UUID,
    duration_sec        NUMERIC(10,2),
    _ingested_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    _run_id             UUID,
    _source             TEXT         DEFAULT 'oltp'
);
CREATE INDEX IF NOT EXISTS idx_stg_scans_company_started
    ON stg_scans (company_id, started_at DESC);

-- Función de upsert idempotente
CREATE OR REPLACE FUNCTION etl_load_stg_scans(p_run_id UUID) RETURNS BIGINT AS $$
DECLARE
    rows_loaded BIGINT;
BEGIN
    INSERT INTO stg_scans AS s (
        scan_id, company_id, token_id, started_at, completed_at,
        status, verdict, risk_score, machine_id_text, player_uuid_canon,
        duration_sec, _run_id
    )
    SELECT
        r.id,
        st.company_id,                                       -- via scan_tokens
        r.token_id,
        r.started_at,
        r.completed_at,
        LOWER(r.status),
        LOWER(r.verdict),
        r.risk_score::numeric(6,2),
        r.machine_id::text,
        CASE WHEN r.player_uuid ~ '^[0-9a-fA-F-]{36}$' THEN r.player_uuid::uuid END,
        EXTRACT(EPOCH FROM (r.completed_at - r.started_at))::numeric(10,2),
        p_run_id
    FROM scans r
    LEFT JOIN scan_tokens st ON st.id = r.token_id
    WHERE r.started_at >= NOW() - INTERVAL '7 days'      -- ventana incremental
    ON CONFLICT (scan_id) DO UPDATE SET
        completed_at = EXCLUDED.completed_at,
        status       = EXCLUDED.status,
        verdict      = EXCLUDED.verdict,
        risk_score   = EXCLUDED.risk_score,
        duration_sec = EXCLUDED.duration_sec,
        _ingested_at = NOW(),
        _run_id      = p_run_id;
    GET DIAGNOSTICS rows_loaded = ROW_COUNT;
    RETURN rows_loaded;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 3 · CLEANED · reglas de negocio, FK enforcement
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cln_scans (
    scan_id        BIGINT       PRIMARY KEY,
    company_id     INTEGER      NOT NULL,
    started_at     TIMESTAMPTZ  NOT NULL,
    completed_at   TIMESTAMPTZ,
    is_completed   BOOLEAN      NOT NULL,
    is_banned      BOOLEAN      NOT NULL,
    risk_bucket    VARCHAR(16)  NOT NULL,
    duration_sec   NUMERIC(10,2),
    _ingested_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    _run_id        UUID
);
CREATE INDEX IF NOT EXISTS idx_cln_scans_company_day
    ON cln_scans (company_id, (started_at::date));

CREATE OR REPLACE FUNCTION etl_load_cln_scans(p_run_id UUID) RETURNS BIGINT AS $$
DECLARE
    rows_loaded BIGINT;
BEGIN
    -- Quality gate: rechazar filas sin company_id (post-F-001 esto debe ser 0)
    PERFORM 1 FROM stg_scans WHERE company_id IS NULL AND _run_id = p_run_id LIMIT 1;
    IF FOUND THEN
        RAISE NOTICE 'stg_scans con company_id NULL detectado en run % — saltando esas filas', p_run_id;
    END IF;

    INSERT INTO cln_scans AS c (
        scan_id, company_id, started_at, completed_at,
        is_completed, is_banned, risk_bucket, duration_sec, _run_id
    )
    SELECT
        s.scan_id,
        s.company_id,
        s.started_at,
        s.completed_at,
        s.status = 'completed',
        s.verdict = 'ban',
        CASE
            WHEN s.risk_score >= 80 THEN 'critical'
            WHEN s.risk_score >= 60 THEN 'high'
            WHEN s.risk_score >= 30 THEN 'medium'
            WHEN s.risk_score IS NULL THEN 'unknown'
            ELSE 'low'
        END,
        s.duration_sec,
        p_run_id
    FROM stg_scans s
    WHERE s.company_id IS NOT NULL
    ON CONFLICT (scan_id) DO UPDATE SET
        is_completed = EXCLUDED.is_completed,
        is_banned    = EXCLUDED.is_banned,
        risk_bucket  = EXCLUDED.risk_bucket,
        duration_sec = EXCLUDED.duration_sec,
        _ingested_at = NOW(),
        _run_id      = p_run_id;
    GET DIAGNOSTICS rows_loaded = ROW_COUNT;
    RETURN rows_loaded;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 4 · AGGREGATED · tablas para dashboards (alternativa a MVs cuando el refresh es caro)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS agg_daily_scan_metrics (
    company_id        INTEGER     NOT NULL,
    day               DATE        NOT NULL,
    total_scans       BIGINT      NOT NULL,
    completed         BIGINT      NOT NULL,
    banned            BIGINT      NOT NULL,
    avg_risk          NUMERIC(6,2),
    p95_duration_sec  NUMERIC(10,2),
    _refreshed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (company_id, day)
);

CREATE OR REPLACE FUNCTION etl_refresh_agg_daily_scan_metrics() RETURNS BIGINT AS $$
DECLARE
    rows_aff BIGINT;
BEGIN
    INSERT INTO agg_daily_scan_metrics AS a (
        company_id, day, total_scans, completed, banned, avg_risk, p95_duration_sec
    )
    SELECT
        company_id,
        started_at::date,
        COUNT(*),
        COUNT(*) FILTER (WHERE is_completed),
        COUNT(*) FILTER (WHERE is_banned),
        AVG(NULLIF(duration_sec, 0))::numeric(10,2) AS p95_dur_placeholder,
        -- p95 real requiere percentile_cont (PG 9.4+)
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_sec)::numeric(10,2)
    FROM cln_scans
    WHERE started_at >= NOW() - INTERVAL '90 days'
    GROUP BY 1, 2
    ON CONFLICT (company_id, day) DO UPDATE SET
        total_scans      = EXCLUDED.total_scans,
        completed        = EXCLUDED.completed,
        banned           = EXCLUDED.banned,
        avg_risk         = EXCLUDED.avg_risk,
        p95_duration_sec = EXCLUDED.p95_duration_sec,
        _refreshed_at    = NOW();
    GET DIAGNOSTICS rows_aff = ROW_COUNT;
    RETURN rows_aff;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 5 · Orquestador (un run = una transacción por stage, run_id compartido)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION etl_run_all() RETURNS UUID AS $$
DECLARE
    rid UUID := gen_random_uuid();
    rin BIGINT;
    rout BIGINT;
    t0 TIMESTAMPTZ;
BEGIN
    -- STG
    t0 := clock_timestamp();
    INSERT INTO etl_runs (run_id, stage, started_at) VALUES (rid, 'stg_scans', t0);
    rout := etl_load_stg_scans(rid);
    UPDATE etl_runs SET finished_at = NOW(), status='ok', rows_out = rout
        WHERE run_id = rid AND stage = 'stg_scans';

    -- CLN
    t0 := clock_timestamp();
    INSERT INTO etl_runs (run_id, stage, started_at) VALUES (rid, 'cln_scans', t0);
    rout := etl_load_cln_scans(rid);
    UPDATE etl_runs SET finished_at = NOW(), status='ok', rows_out = rout
        WHERE run_id = rid AND stage = 'cln_scans';

    -- AGG
    t0 := clock_timestamp();
    INSERT INTO etl_runs (run_id, stage, started_at) VALUES (rid, 'agg_daily', t0);
    rout := etl_refresh_agg_daily_scan_metrics();
    UPDATE etl_runs SET finished_at = NOW(), status='ok', rows_out = rout
        WHERE run_id = rid AND stage = 'agg_daily';

    RETURN rid;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 6 · Quality gates (lanzar manualmente o desde airflow/dbt)
-- ---------------------------------------------------------------------------
-- Stale data alert:
-- SELECT 'stale' AS alert
-- FROM etl_runs
-- WHERE stage='agg_daily' AND status='ok'
-- GROUP BY 1 HAVING MAX(finished_at) < NOW() - INTERVAL '2 hours';

-- Row count drift entre stages (mismo run_id):
-- SELECT run_id, stage, rows_out FROM etl_runs WHERE run_id = $1 ORDER BY started_at;

-- ============================================================================
-- FIN — orquestar con pg_cron, airflow, dbt o cron del SO.
-- ============================================================================
