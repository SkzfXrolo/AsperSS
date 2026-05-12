-- ============================================================================
-- Argus Projects — Pack 48-H Round 4 · #121
-- reports/monthly-summary.sql
-- ----------------------------------------------------------------------------
-- Resumen mensual por empresa: scans, ban rate, top violadores, AI confidence.
-- Parámetros via psql:
--   \set p_company_id 14
--   \set p_month '2026-04-01'
--   \i scripts/db/reports/monthly-summary.sql
-- ============================================================================

-- header con parámetros (si no setearon, default mes anterior global)
SELECT
    COALESCE(:'p_company_id', '0')::int      AS company_id_filter,
    COALESCE(:'p_month', date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::text) AS month_start;

\set company_id COALESCE(:'p_company_id', '0')::int
\set month_start COALESCE(:'p_month', date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::text)

-- ---------------------------------------------------------------------------
-- 1 · Header
-- ---------------------------------------------------------------------------
WITH params AS (
    SELECT
        (:'p_month')::date                              AS m_start,
        ((:'p_month')::date + INTERVAL '1 month')::date  AS m_end,
        NULLIF((:'p_company_id')::int, 0)                AS cid_filter
)
SELECT
    'ARGUS MONTHLY REPORT'  AS report,
    p.cid_filter            AS company_id,
    p.m_start, p.m_end,
    NOW()                   AS generated_at,
    'v1.0'                  AS version
FROM params p;

-- ---------------------------------------------------------------------------
-- 2 · Resumen por empresa
-- ---------------------------------------------------------------------------
WITH params AS (
    SELECT (:'p_month')::date AS m_start,
           ((:'p_month')::date + INTERVAL '1 month')::date AS m_end,
           NULLIF((:'p_company_id')::int, 0) AS cid_filter
)
SELECT
    s.company_id,
    COUNT(*)                                                AS total_scans,
    COUNT(*) FILTER (WHERE s.status='completed')            AS completed,
    COUNT(*) FILTER (WHERE s.verdict='ban')                 AS banned,
    COUNT(*) FILTER (WHERE s.verdict='suspicious')          AS suspicious,
    ROUND(100.0 * COUNT(*) FILTER (WHERE s.verdict='ban')
                  / NULLIF(COUNT(*), 0), 2)                  AS ban_rate_pct,
    AVG(s.risk_score)::numeric(6,2)                          AS avg_risk_score,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY s.risk_score) AS p95_risk_score,
    COUNT(DISTINCT s.minecraft_username)                     AS unique_players
FROM scans s, params p
WHERE s.started_at >= p.m_start
  AND s.started_at  < p.m_end
  AND (p.cid_filter IS NULL OR s.company_id = p.cid_filter)
GROUP BY s.company_id
ORDER BY total_scans DESC;

-- ---------------------------------------------------------------------------
-- 3 · Top 10 violators (jugadores con más bans)
-- ---------------------------------------------------------------------------
WITH params AS (
    SELECT (:'p_month')::date AS m_start,
           ((:'p_month')::date + INTERVAL '1 month')::date AS m_end,
           NULLIF((:'p_company_id')::int, 0) AS cid_filter
)
SELECT
    s.company_id,
    s.minecraft_username,
    COUNT(*)                                                AS total_scans,
    COUNT(*) FILTER (WHERE s.verdict='ban')                 AS bans,
    AVG(s.risk_score)::numeric(6,2)                         AS avg_risk
FROM scans s, params p
WHERE s.started_at >= p.m_start
  AND s.started_at  < p.m_end
  AND (p.cid_filter IS NULL OR s.company_id = p.cid_filter)
GROUP BY s.company_id, s.minecraft_username
HAVING COUNT(*) FILTER (WHERE s.verdict='ban') >= 3
ORDER BY bans DESC, avg_risk DESC
LIMIT 10;

-- ---------------------------------------------------------------------------
-- 4 · Distribución diaria
-- ---------------------------------------------------------------------------
WITH params AS (
    SELECT (:'p_month')::date AS m_start,
           ((:'p_month')::date + INTERVAL '1 month')::date AS m_end,
           NULLIF((:'p_company_id')::int, 0) AS cid_filter
)
SELECT
    date_trunc('day', s.started_at)::date  AS day,
    COUNT(*)                                AS scans,
    COUNT(*) FILTER (WHERE s.verdict='ban') AS bans
FROM scans s, params p
WHERE s.started_at >= p.m_start
  AND s.started_at  < p.m_end
  AND (p.cid_filter IS NULL OR s.company_id = p.cid_filter)
GROUP BY day
ORDER BY day;

-- ============================================================================
-- FIN
-- ============================================================================
