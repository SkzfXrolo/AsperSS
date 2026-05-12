-- ============================================================================
-- Argus Projects — Pack 48-H Round 2
-- explain-templates.sql
-- ----------------------------------------------------------------------------
-- 30 plantillas EXPLAIN (ANALYZE, BUFFERS) para ejecutar en producción
-- (Render psql) con parámetros reales sustituidos manualmente.
--
-- USO:
--   \set company_id 123
--   \set player_uuid 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f explain-templates.sql
--
-- O copiar bloque por bloque y reemplazar :company_id por literales.
--
-- RED FLAGS comunes:
--   * Seq Scan on scans / scan_results / plugin_violations / ai_decisions_log
--     con rows > 100k estimados
--   * Sort Method: external merge / Disk: true (spill)
--   * Nested Loop con inner rows > 1000
--   * Bitmap Heap Scan con Recheck Cond alto (>20% rows)
--   * Planning Time >> Execution Time repetidamente (bloat de stats)
-- ============================================================================

-- ------------------------------------------------------------------ TEMPLATE 01
-- Q01 Daily summary: issue_type counts for hacks yesterday
-- EXPECT: Hash Join or Merge Join; index scan on scans.started_at range
-- RED FLAG: Seq Scan on scan_results full table
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT sr.issue_type, COUNT(*) AS n
FROM   scan_results sr
JOIN   scans s ON sr.scan_id = s.id
WHERE  s.verdict = 'hack'
  AND  s.started_at >= CURRENT_DATE - INTERVAL '1 day'
  AND  s.started_at <  CURRENT_DATE
GROUP BY sr.issue_type
ORDER BY n DESC
LIMIT 3;

-- ------------------------------------------------------------------ TEMPLATE 02
-- Q01 variant BAD (current code style) — DATE() prevents index use
-- EXPECT: same as 01 but often worse plan
-- RED FLAG: Filter: date(started_at) = ... on Seq Scan
EXPLAIN (ANALYZE, BUFFERS)
SELECT sr.issue_type, COUNT(*) AS n
FROM   scan_results sr
JOIN   scans s ON sr.scan_id = s.id
WHERE  s.verdict = 'hack'
  AND  DATE(s.started_at) = CURRENT_DATE - 1
GROUP BY sr.issue_type;

-- ------------------------------------------------------------------ TEMPLATE 03
-- Q03 Health: total scans
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) FROM scans;

-- ------------------------------------------------------------------ TEMPLATE 04
-- Q04 running scans
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) FROM scans WHERE status = 'running';

-- ------------------------------------------------------------------ TEMPLATE 05
-- Q05 distinct machines
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(DISTINCT machine_id) FROM scans
WHERE machine_id IS NOT NULL AND machine_id <> '';

-- ------------------------------------------------------------------ TEMPLATE 06
-- Q06 critical results
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) FROM scan_results WHERE alert_level = 'CRITICAL';

-- ------------------------------------------------------------------ TEMPLATE 07
-- Q08 active tokens
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) FROM scan_tokens WHERE is_active = TRUE;

-- ------------------------------------------------------------------ TEMPLATE 08
-- Q09 verdict histogram fragment
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) FROM scans WHERE verdict = 'clean';

-- ------------------------------------------------------------------ TEMPLATE 09
-- Q10 avg duration
EXPLAIN (ANALYZE, BUFFERS)
SELECT AVG(scan_duration) FROM scans
WHERE scan_duration IS NOT NULL AND scan_duration > 0;

-- ------------------------------------------------------------------ TEMPLATE 10
-- Q11 short_code collision check (replace :code)
EXPLAIN (ANALYZE, BUFFERS)
SELECT 1 FROM scan_tokens WHERE short_code = 'REPLACE6';

-- ------------------------------------------------------------------ TEMPLATE 11
-- Q12 plugin key lookup (replace :api_key)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, company_id, is_active, daily_quota, used_today
FROM   company_plugin_keys
WHERE  api_key = 'REPLACE_FULL_API_KEY';

-- ------------------------------------------------------------------ TEMPLATE 12
-- Q13 violations count by company (replace :cid)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS c
FROM   plugin_violations
WHERE  company_id = 123;

-- ------------------------------------------------------------------ TEMPLATE 13
-- Q14 violations group by level
EXPLAIN (ANALYZE, BUFFERS)
SELECT level, COUNT(*) AS c
FROM   plugin_violations
WHERE  company_id = 123
  AND  created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
GROUP BY level;

-- ------------------------------------------------------------------ TEMPLATE 14
-- Q15 ai_weights
EXPLAIN (ANALYZE, BUFFERS)
SELECT weights_json FROM ai_weights WHERE company_id = 123;

-- ------------------------------------------------------------------ TEMPLATE 15
-- Q16 ai_player_scores point lookup
EXPLAIN (ANALYZE, BUFFERS)
SELECT score, last_evaluated_at, confidence
FROM   ai_player_scores
WHERE  company_id = 123
  AND  player_uuid = '00000000-0000-0000-0000-000000000000';

-- ------------------------------------------------------------------ TEMPLATE 16
-- Q18 ai_model_state
EXPLAIN (ANALYZE, BUFFERS)
SELECT state_json FROM ai_model_state
WHERE  company_id = 123 AND model_kind = 'logreg';

-- ------------------------------------------------------------------ TEMPLATE 17
-- Q19 ai_decisions_log recent (replace :cid)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, action, score, created_at
FROM   ai_decisions_log
WHERE  company_id = 123
ORDER BY created_at DESC
LIMIT 50;

-- ------------------------------------------------------------------ TEMPLATE 18
-- Q20 ai_player_profiles company pull (LIMIT recommended in prod test)
EXPLAIN (ANALYZE, BUFFERS)
SELECT player_uuid, last_updated_at
FROM   ai_player_profiles
WHERE  company_id = 123
ORDER BY last_updated_at DESC
LIMIT 500;

-- ------------------------------------------------------------------ TEMPLATE 19
-- Q21 ai_feedback list
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, label, created_at
FROM   ai_feedback
WHERE  company_id = 123
ORDER BY created_at DESC
LIMIT 100;

-- ------------------------------------------------------------------ TEMPLATE 20
-- Q22 ai_auto_labels filter confidence
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, source, label, confidence
FROM   ai_auto_labels
WHERE  company_id = 123 AND confidence >= 0.55
ORDER BY created_at DESC
LIMIT 200;

-- ------------------------------------------------------------------ TEMPLATE 21
-- Q23 double EXISTS pattern
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS c
FROM   ai_decisions_log d
WHERE  d.company_id = 123
  AND  EXISTS (SELECT 1 FROM ai_feedback f WHERE f.decision_id = d.id)
  AND  EXISTS (SELECT 1 FROM ai_auto_labels al WHERE al.decision_id = d.id);

-- ------------------------------------------------------------------ TEMPLATE 22
-- Q25 double NOT EXISTS (unlabeled decisions)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS c
FROM   ai_decisions_log d
WHERE  d.company_id = 123
  AND  NOT EXISTS (SELECT 1 FROM ai_feedback f WHERE f.decision_id = d.id)
  AND  NOT EXISTS (SELECT 1 FROM ai_auto_labels al WHERE al.decision_id = d.id);

-- ------------------------------------------------------------------ TEMPLATE 23
-- Q25 variant SEMI-JOIN rewrite (compare cost vs template 22)
EXPLAIN (ANALYZE, BUFFERS)
SELECT COUNT(*) AS c
FROM   ai_decisions_log d
LEFT JOIN ai_feedback f ON f.decision_id = d.id
LEFT JOIN ai_auto_labels al ON al.decision_id = d.id
WHERE d.company_id = 123
  AND f.id IS NULL AND al.id IS NULL;

-- ------------------------------------------------------------------ TEMPLATE 24
-- Q27 MAX(created_at) violations per player
EXPLAIN (ANALYZE, BUFFERS)
SELECT MAX(created_at) AS last_v
FROM   plugin_violations
WHERE  company_id = 123 AND player_uuid = '00000000-0000-0000-0000-000000000000';

-- ------------------------------------------------------------------ TEMPLATE 25
-- Q28 leaderboard ai_player_scores
EXPLAIN (ANALYZE, BUFFERS)
SELECT player_name, score
FROM   ai_player_scores
WHERE  company_id = 123
ORDER BY score DESC
LIMIT 20;

-- ------------------------------------------------------------------ TEMPLATE 26
-- Q29 decisions by action
EXPLAIN (ANALYZE, BUFFERS)
SELECT action, COUNT(*) AS c
FROM   ai_decisions_log
WHERE  company_id = 123
  AND  created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY action;

-- ------------------------------------------------------------------ TEMPLATE 27
-- Q30 recent decisions with player ordering
EXPLAIN (ANALYZE, BUFFERS)
SELECT player_name, score, created_at
FROM   ai_decisions_log
WHERE  company_id = 123
ORDER BY created_at DESC
LIMIT 50;

-- ------------------------------------------------------------------ TEMPLATE 28
-- staff_audit_log paginated (adjust user filter)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, user_id, action, scan_id, created_at
FROM   staff_audit_log
ORDER BY created_at DESC
LIMIT 50;

-- ------------------------------------------------------------------ TEMPLATE 29
-- scan_results for one scan (hot path get_scan)
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, issue_type, alert_level, file_hash
FROM   scan_results
WHERE  scan_id = 12345
ORDER BY id;

-- ------------------------------------------------------------------ TEMPLATE 30
-- push_subscriptions full pull (webpush broadcast path)
-- RED FLAG: Seq Scan sin LIMIT — si tabla crece, problema severo
EXPLAIN (ANALYZE, BUFFERS)
SELECT endpoint, p256dh, auth FROM push_subscriptions LIMIT 1000;

-- ============================================================================
-- FIN — revisar "Planning Time" vs "Execution Time" y adjuntar salida a ticket
-- ============================================================================
