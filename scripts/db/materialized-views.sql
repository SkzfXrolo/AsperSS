-- ============================================================================
-- Argus Projects — Pack 48-H Round 3 · #90
-- materialized-views.sql
-- ----------------------------------------------------------------------------
-- Definiciones idempotentes de las 4 MVs propuestas + helpers.
-- ⚠️  No ejecutar contra prod sin staging. CONCURRENTLY exige unique index.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Helper · tabla de auditoría de refresh
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mv_refresh_log (
    id            BIGSERIAL PRIMARY KEY,
    mv_name       TEXT        NOT NULL,
    refreshed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    duration_ms   INTEGER,
    rows_after    BIGINT,
    error_msg     TEXT
);

CREATE INDEX IF NOT EXISTS idx_mv_refresh_log_name_time
    ON mv_refresh_log (mv_name, refreshed_at DESC);

-- ---------------------------------------------------------------------------
-- Función genérica de refresh con auditoría + lock advisory
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_refresh_mv(p_mv TEXT, p_concurrent BOOLEAN DEFAULT TRUE)
RETURNS VOID AS $$
DECLARE
    t0 TIMESTAMPTZ := clock_timestamp();
    rows_after BIGINT;
    lock_key BIGINT := abs(hashtextextended(p_mv, 0));
BEGIN
    IF NOT pg_try_advisory_lock(lock_key) THEN
        INSERT INTO mv_refresh_log (mv_name, error_msg)
        VALUES (p_mv, 'lock busy — skipped');
        RETURN;
    END IF;

    BEGIN
        IF p_concurrent THEN
            EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I', p_mv);
        ELSE
            EXECUTE format('REFRESH MATERIALIZED VIEW %I', p_mv);
        END IF;
        EXECUTE format('SELECT COUNT(*) FROM %I', p_mv) INTO rows_after;
        INSERT INTO mv_refresh_log (mv_name, duration_ms, rows_after)
        VALUES (p_mv, (EXTRACT(EPOCH FROM clock_timestamp()-t0)*1000)::int, rows_after);
    EXCEPTION WHEN OTHERS THEN
        INSERT INTO mv_refresh_log (mv_name, duration_ms, error_msg)
        VALUES (p_mv, (EXTRACT(EPOCH FROM clock_timestamp()-t0)*1000)::int, SQLERRM);
        PERFORM pg_advisory_unlock(lock_key);
        RAISE;
    END;

    PERFORM pg_advisory_unlock(lock_key);
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- MV 1 · mv_daily_scan_stats
-- ---------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_daily_scan_stats CASCADE;
CREATE MATERIALIZED VIEW mv_daily_scan_stats AS
SELECT
    -- placeholder hasta que F-001 agregue scans.company_id;
    -- actualmente derivamos a través de scan_tokens si existe.
    COALESCE(st.company_id, -1)              AS company_id,
    date_trunc('day', s.started_at)::date     AS day,
    COUNT(*)                                  AS total_scans,
    COUNT(*) FILTER (WHERE s.status='completed')        AS completed,
    COUNT(*) FILTER (WHERE s.verdict='ban')             AS banned,
    COUNT(*) FILTER (WHERE s.status='error')            AS errored,
    AVG(EXTRACT(EPOCH FROM (s.completed_at - s.started_at)))::numeric(10,2)
                                              AS avg_duration_sec,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.verdict='ban') / NULLIF(COUNT(*),0), 2)
                                              AS ban_rate_pct,
    AVG(s.risk_score)::numeric(10,2)          AS avg_risk_score,
    MAX(s.completed_at)                       AS last_scan_completed
FROM scans s
LEFT JOIN scan_tokens st ON st.id = s.token_id
WHERE s.started_at >= NOW() - INTERVAL '13 months'
GROUP BY 1, 2;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_daily_scan_stats
    ON mv_daily_scan_stats (company_id, day);
CREATE INDEX IF NOT EXISTS idx_mv_daily_scan_stats_day
    ON mv_daily_scan_stats (day DESC);

-- ---------------------------------------------------------------------------
-- MV 2 · mv_player_profiles_summary
-- ---------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_player_profiles_summary CASCADE;
CREATE MATERIALIZED VIEW mv_player_profiles_summary AS
SELECT
    p.company_id,
    p.player_uuid,
    p.player_name,
    p.total_scans,
    p.total_violations,
    p.last_scan_at,
    p.last_violation_type,
    p.avg_risk_score,
    CASE
        WHEN p.avg_risk_score >= 80 THEN 'critical'
        WHEN p.avg_risk_score >= 60 THEN 'high'
        WHEN p.avg_risk_score >= 30 THEN 'medium'
        ELSE 'low'
    END                                    AS risk_tier,
    (SELECT COUNT(*) FROM ban_history b
     WHERE b.company_id = p.company_id AND b.player_uuid = p.player_uuid)
                                          AS ban_count
FROM ai_player_profiles p;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_player_profiles_summary
    ON mv_player_profiles_summary (company_id, player_uuid);
CREATE INDEX IF NOT EXISTS idx_mv_player_profiles_summary_risk
    ON mv_player_profiles_summary (company_id, avg_risk_score DESC NULLS LAST);

-- ---------------------------------------------------------------------------
-- MV 3 · mv_oracle_confidence_distribution
-- ---------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_oracle_confidence_distribution CASCADE;
CREATE MATERIALIZED VIEW mv_oracle_confidence_distribution AS
SELECT
    company_id,
    (FLOOR(confidence_score / 5) * 5)::int  AS bucket_5pct_lower,
    COUNT(*)                                AS count,
    AVG(confidence_score)::numeric(10,2)    AS avg_score,
    ROUND(100.0 * COUNT(*) FILTER (WHERE verdict='ban') / NULLIF(COUNT(*),0), 2)
                                            AS ban_pct_in_bucket
FROM ai_decisions_log
WHERE created_at >= NOW() - INTERVAL '90 days'
GROUP BY 1, 2;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_oracle_conf_dist
    ON mv_oracle_confidence_distribution (company_id, bucket_5pct_lower);

-- ---------------------------------------------------------------------------
-- MV 4 · mv_plugin_health_metrics
-- ---------------------------------------------------------------------------
DROP MATERIALIZED VIEW IF EXISTS mv_plugin_health_metrics CASCADE;
CREATE MATERIALIZED VIEW mv_plugin_health_metrics AS
SELECT
    p.company_id,
    p.server_name,
    p.last_seen,
    COUNT(s.id) FILTER (WHERE s.started_at >= NOW() - INTERVAL '1 hour') AS scans_last_hour,
    COUNT(s.id) FILTER (WHERE s.started_at >= NOW() - INTERVAL '1 day')  AS scans_last_day,
    COUNT(s.id) FILTER (WHERE s.status='error' AND s.started_at >= NOW() - INTERVAL '1 day')
                                                                AS errors_last_day,
    CASE
        WHEN p.last_seen >= NOW() - INTERVAL '5 minutes'   THEN 'healthy'
        WHEN p.last_seen >= NOW() - INTERVAL '1 hour'      THEN 'stale'
        ELSE                                                   'down'
    END                                                          AS health_status
FROM plugin_servers p
LEFT JOIN scan_tokens t ON t.plugin_key_id = p.plugin_key_id
LEFT JOIN scans s ON s.token_id = t.id AND s.started_at >= NOW() - INTERVAL '1 day'
GROUP BY p.company_id, p.server_name, p.last_seen;

CREATE UNIQUE INDEX IF NOT EXISTS uq_mv_plugin_health
    ON mv_plugin_health_metrics (company_id, server_name);

-- ---------------------------------------------------------------------------
-- Refresh planificado (ejemplo via pg_cron)
-- ---------------------------------------------------------------------------
-- SELECT cron.schedule('mv_plugin_health',  '* * * * *', $$SELECT argus_refresh_mv('mv_plugin_health_metrics')$$);
-- SELECT cron.schedule('mv_daily_scan',     '*/5 * * * *', $$SELECT argus_refresh_mv('mv_daily_scan_stats')$$);
-- SELECT cron.schedule('mv_player_summary', '*/15 * * * *', $$SELECT argus_refresh_mv('mv_player_profiles_summary')$$);
-- SELECT cron.schedule('mv_oracle_conf',    '*/30 * * * *', $$SELECT argus_refresh_mv('mv_oracle_confidence_distribution')$$);

-- ---------------------------------------------------------------------------
-- Refresh inicial (manual; CONCURRENTLY requiere segunda llamada después de populate)
-- ---------------------------------------------------------------------------
-- REFRESH MATERIALIZED VIEW mv_daily_scan_stats;
-- REFRESH MATERIALIZED VIEW mv_player_profiles_summary;
-- REFRESH MATERIALIZED VIEW mv_oracle_confidence_distribution;
-- REFRESH MATERIALIZED VIEW mv_plugin_health_metrics;
