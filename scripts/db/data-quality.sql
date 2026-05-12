-- ============================================================================
-- Argus Projects — Pack 48-H Round 2
-- data-quality.sql
-- ----------------------------------------------------------------------------
-- 20 invariantes de calidad de datos ADICIONALES a integrity-checks.sql R1.
-- count > 0 => investigar.
-- ============================================================================

-- DQ01) scan_results huérfanos (sin scan padre)
SELECT COUNT(*) AS dq01_orphan_scan_results
FROM   scan_results sr
LEFT   JOIN scans s ON s.id = sr.scan_id
WHERE  sr.scan_id IS NOT NULL AND s.id IS NULL;

-- DQ02) verdict_history huérfano
SELECT COUNT(*) AS dq02_orphan_verdict_history
FROM   verdict_history vh
LEFT   JOIN scans s ON s.id = vh.scan_id
WHERE  s.id IS NULL;

-- DQ03) scan_notes huérfano
SELECT COUNT(*) AS dq03_orphan_scan_notes
FROM   scan_notes sn
LEFT   JOIN scans s ON s.id = sn.scan_id
WHERE  s.id IS NULL;

-- DQ04) Timestamps en el futuro (> 1 día clock skew)
SELECT COUNT(*) AS dq04_scans_future_started
FROM   scans
WHERE  started_at > NOW() + INTERVAL '1 day';

-- DQ05) completed_at anterior a started_at
SELECT COUNT(*) AS dq05_scan_time_inversion
FROM   scans
WHERE  completed_at IS NOT NULL AND started_at IS NOT NULL
  AND  completed_at < started_at;

-- DQ06) risk_score fuera 0..100
SELECT COUNT(*) AS dq06_risk_out_of_range
FROM   scans
WHERE  risk_score IS NOT NULL AND (risk_score < 0 OR risk_score > 100);

-- DQ07) minecraft_username demasiado largo (> 64 chars MC típico)
SELECT COUNT(*) AS dq07_mc_name_too_long
FROM   scans
WHERE  minecraft_username IS NOT NULL AND length(minecraft_username) > 64;

-- DQ08) player_uuid con formato inválido (no UUID v4 regex simplificado)
SELECT COUNT(*) AS dq08_bad_uuid_plugin_violations
FROM   plugin_violations
WHERE  player_uuid IS NOT NULL
  AND  player_uuid !~ '^[0-9a-fA-F-]{36}$';

-- DQ09) ai_decisions_log sin company_id pero con plugin_key_id (debería inferirse)
SELECT COUNT(*) AS dq09_decision_missing_company
FROM   ai_decisions_log
WHERE  company_id IS NULL AND plugin_key_id IS NOT NULL;

-- DQ10) duplicate short_code (should be impossible)
SELECT COUNT(*) AS dq10_dup_short_code
FROM   (
  SELECT short_code FROM scan_tokens WHERE short_code IS NOT NULL
  GROUP BY short_code HAVING COUNT(*) > 1
) t;

-- DQ11) staff_feedback verified_at en futuro
SELECT COUNT(*) AS dq11_feedback_future
FROM   staff_feedback
WHERE  verified_at > NOW() + INTERVAL '1 day';

-- DQ12) learned_hashes file_hash longitud != 64
SELECT COUNT(*) AS dq12_bad_hash_length
FROM   learned_hashes
WHERE  length(file_hash) <> 64;

-- DQ13) discord_queue data JSON inválido (PG: catch exceptions en app; aquí chequeo IS NOT NULL only)
-- Skip strict JSON validate (costoso); placeholder:
SELECT COUNT(*) AS dq13_discord_null_data
FROM   discord_queue
WHERE  data IS NULL;

-- DQ14) statistics duplicate dates
SELECT COUNT(*) AS dq14_stats_dup_date
FROM   (
  SELECT date FROM statistics GROUP BY date HAVING COUNT(*) > 1
) t;

-- DQ15) ai_training_history con métricas > 1.0 (deberían ser ratios)
SELECT COUNT(*) AS dq15_training_metrics_oob
FROM   ai_training_history
WHERE  accuracy > 1.0 OR precision > 1.0 OR recall > 1.0 OR f1 > 1.0;

-- DQ16) plugin_violations level no canónico
SELECT COUNT(*) AS dq16_bad_violation_level
FROM   plugin_violations
WHERE  level IS NOT NULL
  AND  upper(level) NOT IN ('LOW','MID','HIGH','CRITICAL');

-- DQ17) scans verdict no canónico
SELECT COUNT(*) AS dq17_bad_verdict
FROM   scans
WHERE  verdict IS NOT NULL AND verdict NOT IN ('clean','hack','pending','');

-- DQ18) empty machine_id string vs NULL inconsistency
SELECT COUNT(*) AS dq18_machine_id_empty_string
FROM   scans
WHERE  machine_id = '';

-- DQ19) ai_player_profiles feature_vector_json vacío
SELECT COUNT(*) AS dq19_empty_feature_vector
FROM   ai_player_profiles
WHERE  feature_vector_json IS NULL OR length(trim(feature_vector_json)) < 3;

-- DQ20) company_plugin_keys api_key sin prefijo esperado
SELECT COUNT(*) AS dq20_api_key_bad_prefix
FROM   company_plugin_keys
WHERE  api_key NOT LIKE 'argus_pk_%';
