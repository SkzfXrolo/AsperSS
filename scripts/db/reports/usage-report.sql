-- ============================================================================
-- Argus Projects — Pack 48-H Round 4 · #121
-- reports/usage-report.sql
-- ----------------------------------------------------------------------------
-- Métricas de uso por empresa para billing. Output JSON para API.
-- Parámetros:
--   \set p_period_start '2026-04-01'
--   \set p_period_end   '2026-05-01'
-- ============================================================================

\set period_start COALESCE(:'p_period_start', (CURRENT_DATE - INTERVAL '30 days')::text)
\set period_end   COALESCE(:'p_period_end',   CURRENT_DATE::text)

-- ---------------------------------------------------------------------------
-- 1 · Métricas core por empresa
-- ---------------------------------------------------------------------------
SELECT
    s.company_id,
    c.name                         AS company_name,
    c.plan,
    (:'p_period_start')::date      AS period_start,
    (:'p_period_end')::date        AS period_end,
    COUNT(*)                       AS scans_count,
    COUNT(DISTINCT s.minecraft_username)
                                   AS unique_players,
    COUNT(*) FILTER (WHERE s.verdict='ban')   AS bans,
    COUNT(DISTINCT t.plugin_key_id)           AS active_plugin_keys,
    SUM(EXTRACT(EPOCH FROM (s.completed_at - s.started_at)))::int
                                   AS total_scan_seconds,
    pg_size_pretty(0::bigint)      AS storage_estimated_placeholder  -- TODO: per-tenant size
FROM scans s
JOIN companies c     ON c.id = s.company_id
LEFT JOIN scan_tokens t ON t.id = s.token_id
WHERE s.started_at >= (:'p_period_start')::timestamp
  AND s.started_at  < (:'p_period_end')::timestamp
GROUP BY s.company_id, c.name, c.plan
ORDER BY scans_count DESC;

-- ---------------------------------------------------------------------------
-- 2 · Overage detection (clientes pasados de su plan)
-- ---------------------------------------------------------------------------
WITH plan_caps(plan, monthly_scans_cap) AS (
    VALUES
        ('free',         1000),
        ('pro',         50000),
        ('enterprise', 1000000)
)
SELECT
    s.company_id,
    c.name, c.plan,
    pc.monthly_scans_cap,
    COUNT(*) AS scans_in_period,
    GREATEST(0, COUNT(*) - pc.monthly_scans_cap) AS overage,
    CASE WHEN COUNT(*) > pc.monthly_scans_cap THEN 'OVER' ELSE 'OK' END AS status
FROM scans s
JOIN companies c ON c.id = s.company_id
LEFT JOIN plan_caps pc ON pc.plan = c.plan
WHERE s.started_at >= (:'p_period_start')::timestamp
  AND s.started_at  < (:'p_period_end')::timestamp
GROUP BY s.company_id, c.name, c.plan, pc.monthly_scans_cap
HAVING pc.monthly_scans_cap IS NOT NULL
ORDER BY overage DESC, scans_in_period DESC;
