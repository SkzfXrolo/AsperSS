-- ============================================================================
-- Argus Projects — Pack 48-H Round 2
-- tenant-isolation-checks.sql
-- ----------------------------------------------------------------------------
-- 15 queries: count > 0 => posible ALERT cross-tenant leak.
-- Ejecutar contra réplica read-only. Reemplazar :cid_a y :cid_b con IDs reales.
-- Postcondición: F-001 (scans.company_id) debe existir para checks S01-S03.
-- ============================================================================

\set cid_a 1
\set cid_b 2

-- S01) [REQUIRES columna scans.company_id — migración F-001] Coherencia scan vs plugin key
-- Hasta entonces: omitir o ejecutar sólo en staging post-migración.
-- SELECT COUNT(*) AS alert_s01_cross_company_scan_token
-- FROM   scans s
-- JOIN   scan_tokens st ON st.id = s.token_id
-- JOIN   company_plugin_keys k ON k.id = st.plugin_key_id
-- WHERE  s.company_id IS NOT NULL AND k.company_id IS NOT NULL AND s.company_id <> k.company_id;
SELECT 0::bigint AS alert_s01_skipped_until_f001;

-- S02) plugin_violations.company_id distinto de company_plugin_keys.company_id
SELECT COUNT(*) AS alert_s02_violation_key_mismatch
FROM   plugin_violations pv
JOIN   company_plugin_keys k ON k.id = pv.plugin_key_id
WHERE  pv.plugin_key_id IS NOT NULL
  AND  pv.company_id IS NOT NULL
  AND  pv.company_id <> k.company_id;

-- S03) ai_decisions_log.company_id vs plugin_key company
SELECT COUNT(*) AS alert_s03_decision_key_mismatch
FROM   ai_decisions_log d
JOIN   company_plugin_keys k ON k.id = d.plugin_key_id
WHERE  d.plugin_key_id IS NOT NULL
  AND  d.company_id IS NOT NULL
  AND  d.company_id <> k.company_id;

-- S04) ai_feedback.company_id distinto de ai_decisions_log.company_id (join por decision_id)
SELECT COUNT(*) AS alert_s04_feedback_decision_company
FROM   ai_feedback f
JOIN   ai_decisions_log d ON d.id = f.decision_id
WHERE  f.decision_id IS NOT NULL
  AND  f.company_id <> d.company_id;

-- S05) ai_auto_labels vs decisions company mismatch
SELECT COUNT(*) AS alert_s05_autolabel_decision_company
FROM   ai_auto_labels al
JOIN   ai_decisions_log d ON d.id = al.decision_id
WHERE  al.decision_id IS NOT NULL
  AND  al.company_id <> d.company_id;

-- S06) ai_player_scores.company_id inconsistente con última violation del mismo uuid
-- (heurística: si hay violation reciente con company distinta → alert)
SELECT COUNT(*) AS alert_s06_score_vs_violation_company
FROM   ai_player_scores aps
JOIN   LATERAL (
    SELECT company_id FROM plugin_violations pv
    WHERE pv.player_uuid = aps.player_uuid
    ORDER BY created_at DESC LIMIT 1
) lv ON true
WHERE aps.company_id <> lv.company_id;

-- S07) users.company_id NULL pero roles contienen company_admin (JSON text)
SELECT COUNT(*) AS alert_s07_company_admin_without_company
FROM   users
WHERE  company_id IS NULL
  AND  roles::text ILIKE '%company_admin%';

-- S08) registration_tokens.company_id no coincide con empresa del created_by user
SELECT COUNT(*) AS alert_s08_regtoken_user_company
FROM   registration_tokens rt
JOIN   users u ON u.id = rt.created_by
WHERE  rt.company_id IS NOT NULL
  AND  u.company_id IS NOT NULL
  AND  rt.company_id <> u.company_id;

-- S09) ai_player_profiles duplicados cross-company mismo uuid (imposible si UK existe; detecta corrupción)
SELECT COUNT(*) AS alert_s09_uuid_multi_company
FROM   (
  SELECT player_uuid FROM ai_player_profiles GROUP BY player_uuid HAVING COUNT(DISTINCT company_id) > 1
) t;

-- S10) scan_tokens.created_by username pertenece a otra empresa que plugin_key_id resolvería
-- (complejo; simplificado: token con plugin_key_id cuya company no coincide con inferencia)
SELECT COUNT(*) AS alert_s10_token_plugin_inconsistent
FROM   scan_tokens st
JOIN   company_plugin_keys k ON k.id = st.plugin_key_id
JOIN   users u ON u.username = st.created_by
WHERE st.plugin_key_id IS NOT NULL
  AND u.company_id IS NOT NULL
  AND k.company_id <> u.company_id;

-- S11) ai_weights row company_id negativo o NULL (solo 0 permitido para global)
SELECT COUNT(*) AS alert_s11_ai_weights_bad_company
FROM   ai_weights
WHERE  company_id < 0 OR company_id IS NULL;

-- S12) company_settings rows huérfanas
SELECT COUNT(*) AS alert_s12_company_settings_orphan
FROM   company_settings cs
LEFT JOIN companies c ON c.id = cs.company_id
WHERE c.id IS NULL;

-- S13) company_fp_cooldown huérfano
SELECT COUNT(*) AS alert_s13_cooldown_orphan
FROM   company_fp_cooldown cd
LEFT JOIN companies c ON c.id = cd.company_id
WHERE c.id IS NULL;

-- S14) [REQUIRES scans.company_id — F-001] staff_audit vs scan vs user company
SELECT 0::bigint AS alert_s14_skipped_until_f001;

-- S15) Dos empresas comparten mismo api_key (imposible si UNIQUE; detecta corrupción índice)
SELECT COUNT(*) AS alert_s15_duplicate_api_key
FROM   (
  SELECT api_key FROM company_plugin_keys GROUP BY api_key HAVING COUNT(*) > 1
) x;
