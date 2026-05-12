-- ============================================================================
-- Argus Projects — Pack 48-H Round 4 · #121
-- reports/incident-report.sql
-- ----------------------------------------------------------------------------
-- Decisiones Oracle de severidad HIGH/CRITICAL (risk_score >= 60) en las
-- últimas N horas. Sirve para revisión semanal staff.
-- Parámetros:
--   \set p_company_id 14   (opcional, 0 = todas)
--   \set p_hours 168       (default = 1 semana)
-- ============================================================================

\set company_id COALESCE(:'p_company_id', '0')::int
\set hours      COALESCE(:'p_hours', '168')::int

-- ---------------------------------------------------------------------------
-- 1 · Conteo por severidad
-- ---------------------------------------------------------------------------
WITH params AS (
    SELECT NOW() - ((:'p_hours')::int || ' hours')::interval AS since_ts,
           NULLIF((:'p_company_id')::int, 0)                  AS cid_filter
)
SELECT
    argus_score_to_level(d.confidence_score) AS level,
    COUNT(*)                                  AS n,
    AVG(d.confidence_score)::numeric(6,2)     AS avg_conf
FROM ai_decisions_log d, params p
WHERE d.created_at >= p.since_ts
  AND (p.cid_filter IS NULL OR d.company_id = p.cid_filter)
GROUP BY level
ORDER BY level;

-- ---------------------------------------------------------------------------
-- 2 · Decisiones críticas detalle
-- ---------------------------------------------------------------------------
WITH params AS (
    SELECT NOW() - ((:'p_hours')::int || ' hours')::interval AS since_ts,
           NULLIF((:'p_company_id')::int, 0)                  AS cid_filter
)
SELECT
    d.id                                          AS decision_id,
    d.company_id,
    d.player_uuid,
    d.verdict,
    d.confidence_score,
    argus_score_to_level(d.confidence_score)      AS level,
    d.model_version,
    d.created_at,
    s.id                                          AS scan_id,
    s.started_at                                  AS scan_started,
    (SELECT COUNT(*) FROM plugin_violations v WHERE v.scan_id = s.id) AS violation_count
FROM ai_decisions_log d
LEFT JOIN scans s ON s.id = d.scan_id
JOIN params p ON TRUE
WHERE d.created_at >= p.since_ts
  AND d.confidence_score >= 60
  AND (p.cid_filter IS NULL OR d.company_id = p.cid_filter)
ORDER BY d.confidence_score DESC, d.created_at DESC
LIMIT 100;

-- ---------------------------------------------------------------------------
-- 3 · Falsas decisiones reportadas (ai_feedback "wrong")
-- ---------------------------------------------------------------------------
WITH params AS (
    SELECT NOW() - ((:'p_hours')::int || ' hours')::interval AS since_ts,
           NULLIF((:'p_company_id')::int, 0)                  AS cid_filter
)
SELECT
    f.decision_id, d.player_uuid, d.confidence_score,
    f.feedback_type, f.comment, f.created_at
FROM ai_feedback f
JOIN ai_decisions_log d ON d.id = f.decision_id
JOIN params p ON TRUE
WHERE f.created_at >= p.since_ts
  AND f.feedback_type IN ('wrong', 'unfair')
  AND (p.cid_filter IS NULL OR f.company_id = p.cid_filter)
ORDER BY f.created_at DESC
LIMIT 50;
