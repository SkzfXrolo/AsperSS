-- ============================================================================
-- Argus Projects — Pack 48 / subagente H
-- integrity-checks.sql
-- ----------------------------------------------------------------------------
-- 18 queries SELECT que verifican invariantes del esquema.
-- Cada una devuelve 0 rows si el invariante se cumple, >0 si hay violación.
--
-- Uso recomendado:
--   psql ... -f integrity-checks.sql -P pager=off
-- o desde el panel admin, llamando una por una.
--
-- Las queries que devuelvan rows deben investigarse caso por caso.
-- ============================================================================

\timing off
\set ECHO all

-- ────────────────────────────────────────────────────────────────────────────
-- IC-01 · No debería haber `ai_feedback` con `company_id IS NULL`
-- (Pack 42 estableció aislamiento per-tenant)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-01: ai_feedback.company_id NULL' AS check_name,
       COUNT(*)                              AS violations
FROM   ai_feedback
WHERE  company_id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-02 · No debería haber player_uuid duplicado en `ai_player_profiles`
-- para la misma empresa (UNIQUE constraint debería bloquearlo, pero
-- verificar manualmente — UNIQUE puede haberse omitido en SQLite).
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-02: ai_player_profiles dup'  AS check_name,
       company_id, player_uuid, COUNT(*) AS rows_per_pk
FROM   ai_player_profiles
GROUP  BY company_id, player_uuid
HAVING COUNT(*) > 1;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-03 · No debería haber player_uuid duplicado en `ai_player_scores`
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-03: ai_player_scores dup'    AS check_name,
       company_id, player_uuid, COUNT(*) AS rows_per_pk
FROM   ai_player_scores
GROUP  BY company_id, player_uuid
HAVING COUNT(*) > 1;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-04 · `scan_tokens.short_code` no debería tener duplicados
-- (UNIQUE constraint declarada, verificar igual)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-04: scan_tokens.short_code dup' AS check_name,
       short_code, COUNT(*)                AS dup_count
FROM   scan_tokens
WHERE  short_code IS NOT NULL
GROUP  BY short_code
HAVING COUNT(*) > 1;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-05 · `scans.token_id` que apunte a un scan_token inexistente (FK rota)
-- (FK declarada como ON DELETE SET NULL, pero por bugs históricos puede
-- haber referencias inválidas si el SET NULL nunca corrió.)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-05: scans.token_id huerfano' AS check_name,
       s.id, s.token_id
FROM   scans s
LEFT   JOIN scan_tokens st ON st.id = s.token_id
WHERE  s.token_id IS NOT NULL
  AND  st.id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-06 · `scan_results.scan_id` huérfano (FK CASCADE debería evitarlo)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-06: scan_results.scan_id huerfano' AS check_name,
       sr.id, sr.scan_id
FROM   scan_results sr
LEFT   JOIN scans s ON s.id = sr.scan_id
WHERE  sr.scan_id IS NOT NULL
  AND  s.id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-07 · `staff_feedback.result_id` huérfano (FK CASCADE)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-07: staff_feedback.result_id huerfano' AS check_name,
       sf.id, sf.result_id
FROM   staff_feedback sf
LEFT   JOIN scan_results sr ON sr.id = sf.result_id
WHERE  sr.id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-08 · `users.company_id` que apunte a empresa inexistente
-- (FK declarada ON DELETE SET NULL; verificar igual)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-08: users.company_id invalido' AS check_name,
       u.id, u.username, u.company_id
FROM   users u
LEFT   JOIN companies c ON c.id = u.company_id
WHERE  u.company_id IS NOT NULL
  AND  c.id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-09 · `company_plugin_keys.company_id` que apunte a empresa inexistente
-- (FK NO declarada — implícita por convención)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-09: cpk.company_id invalido' AS check_name,
       cpk.id, cpk.company_id, cpk.label
FROM   company_plugin_keys cpk
LEFT   JOIN companies c ON c.id = cpk.company_id
WHERE  c.id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-10 · `plugin_violations.plugin_key_id` huérfano
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-10: pv.plugin_key_id invalido' AS check_name,
       pv.id, pv.plugin_key_id
FROM   plugin_violations pv
LEFT   JOIN company_plugin_keys cpk ON cpk.id = pv.plugin_key_id
WHERE  pv.plugin_key_id IS NOT NULL
  AND  cpk.id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-11 · `ai_decisions_log.company_id` debe coincidir con la empresa
-- de la `plugin_key_id` referenciada (anti tampering / cross-tenant leak)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-11: ai_decisions_log cross-tenant' AS check_name,
       adl.id, adl.company_id AS adl_company,
       cpk.company_id           AS cpk_company,
       adl.plugin_key_id
FROM   ai_decisions_log adl
JOIN   company_plugin_keys cpk ON cpk.id = adl.plugin_key_id
WHERE  adl.plugin_key_id IS NOT NULL
  AND  adl.company_id <> cpk.company_id;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-12 · Verdict status consistency
-- Si scan.verdict = 'hack', debería existir al menos 1 scan_results con
-- alert_level CRITICAL o SOSPECHOSO. Si no, es sospechoso (false positive
-- del staff o verdict manual sin evidencia).
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-12: hack sin evidencia'        AS check_name,
       s.id, s.minecraft_username, s.verdict_by
FROM   scans s
LEFT   JOIN scan_results sr ON sr.scan_id = s.id
                            AND sr.alert_level IN ('CRITICAL', 'SOSPECHOSO', 'MUY_SOSPECHOSO')
WHERE  s.verdict = 'hack'
GROUP  BY s.id, s.minecraft_username, s.verdict_by
HAVING COUNT(sr.id) = 0;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-13 · `verdict_history.scan_id` huérfano (FK CASCADE; redundante)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-13: verdict_history huerfano' AS check_name,
       vh.id, vh.scan_id
FROM   verdict_history vh
LEFT   JOIN scans s ON s.id = vh.scan_id
WHERE  s.id IS NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-14 · `ai_player_scores.score` fuera de rango lógico (0..100)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-14: ai_player_scores fuera de rango' AS check_name,
       id, company_id, player_uuid, score, confidence
FROM   ai_player_scores
WHERE  score < 0 OR score > 100 OR confidence < 0 OR confidence > 1;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-15 · `ai_feedback.label` debe ser 0.0, 0.5 o 1.0 (convención)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-15: ai_feedback.label no-canonico' AS check_name,
       id, company_id, label, source
FROM   ai_feedback
WHERE  label NOT IN (0.0, 0.5, 1.0);

-- ────────────────────────────────────────────────────────────────────────────
-- IC-16 · `staff_trust.trust_score` debe estar en [0, 100]
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-16: staff_trust fuera de rango' AS check_name,
       user_id, trust_score
FROM   staff_trust
WHERE  trust_score < 0 OR trust_score > 100;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-17 · `company_fp_cooldown.threshold_bump` debe estar en [0, 30]
-- (la lógica del compute lo cap a 15, pero rows antiguos pueden tener
-- valores legacy)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-17: cooldown threshold_bump anomalo' AS check_name,
       company_id, threshold_bump, fp_count_24h, overturn_count_24h
FROM   company_fp_cooldown
WHERE  threshold_bump < 0 OR threshold_bump > 30;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-18 · Empresa con ≥1 user pero sin company_settings y is_active=TRUE
-- (la cuenta del usuario podría estar usando thresholds default por accidente)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-18: empresa sin company_settings' AS check_name,
       c.id, c.name, COUNT(u.id) AS user_count
FROM   companies c
JOIN   users u  ON u.company_id = c.id AND u.is_active = TRUE
LEFT   JOIN company_settings cs ON cs.company_id = c.id
WHERE  c.is_active = TRUE
  AND  cs.company_id IS NULL
GROUP  BY c.id, c.name
HAVING COUNT(u.id) > 0;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-19 · scan.verdict_at presente pero verdict NULL (estado inconsistente)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-19: scans.verdict_at sin verdict' AS check_name,
       id, verdict, verdict_at, verdict_by
FROM   scans
WHERE  verdict_at IS NOT NULL
  AND  (verdict IS NULL OR verdict = '' OR verdict = 'pending');

-- ────────────────────────────────────────────────────────────────────────────
-- IC-20 · scan_token expirado pero used_count == 0 (token desperdiciado;
-- no es error pero ayuda a entender la conversion rate)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-20: scan_tokens vencidos sin uso' AS check_name,
       COUNT(*) AS unused_expired_tokens
FROM   scan_tokens
WHERE  expires_at < CURRENT_TIMESTAMP
  AND  used_count = 0
  AND  expires_at > CURRENT_TIMESTAMP - INTERVAL '30 days';

-- ────────────────────────────────────────────────────────────────────────────
-- IC-21 · Empresas duplicadas por LOWER(name) (UNIQUE es case-sensitive)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-21: companies dup case' AS check_name,
       LOWER(name) AS name_lower, COUNT(*) AS dup_count
FROM   companies
GROUP  BY LOWER(name)
HAVING COUNT(*) > 1;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-22 · Usuarios con company_id válido pero la empresa is_active=FALSE
-- (deberían suspenderse — login bloqueado)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-22: users en empresa inactiva' AS check_name,
       u.id, u.username, u.company_id, c.name AS company_name
FROM   users u
JOIN   companies c ON c.id = u.company_id
WHERE  u.is_active = TRUE
  AND  c.is_active = FALSE;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-23 · ai_decisions_log con action='banned' pero el player_uuid sigue
-- generando violations posteriores (ban no efectivo en el plugin)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-23: ban no efectivo' AS check_name,
       adl.id AS decision_id, adl.player_uuid, adl.created_at AS ban_at,
       MAX(pv.created_at) AS last_violation_after_ban
FROM   ai_decisions_log adl
JOIN   plugin_violations pv ON pv.player_uuid = adl.player_uuid
                            AND pv.company_id  = adl.company_id
WHERE  adl.action = 'banned'
  AND  pv.created_at > adl.created_at + INTERVAL '1 hour'
GROUP  BY adl.id, adl.player_uuid, adl.created_at
HAVING COUNT(pv.id) >= 3;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-24 · learned_hack_patterns con UNIQUE constraint violado (race condition)
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-24: lhp duplicado kind+value' AS check_name,
       pattern_kind, pattern_value, COUNT(*) AS dup_count
FROM   learned_hack_patterns
GROUP  BY pattern_kind, pattern_value
HAVING COUNT(*) > 1;

-- ────────────────────────────────────────────────────────────────────────────
-- IC-25 · ai_model_state UNIQUE(company_id, model_kind) violado
-- ────────────────────────────────────────────────────────────────────────────
SELECT 'IC-25: ai_model_state dup' AS check_name,
       company_id, model_kind, COUNT(*) AS dup_count
FROM   ai_model_state
GROUP  BY company_id, model_kind
HAVING COUNT(*) > 1;

-- ============================================================================
-- META · resumen ejecutivo en una sola query (correr al final)
-- ============================================================================

SELECT 'SUMMARY' AS section,
       (SELECT COUNT(*) FROM ai_feedback WHERE company_id IS NULL)                    AS ic01,
       (SELECT COUNT(*) FROM (
            SELECT 1 FROM ai_player_profiles
            GROUP BY company_id, player_uuid HAVING COUNT(*) > 1
        ) t)                                                                          AS ic02,
       (SELECT COUNT(*) FROM scans s LEFT JOIN scan_tokens st ON st.id=s.token_id
        WHERE s.token_id IS NOT NULL AND st.id IS NULL)                               AS ic05,
       (SELECT COUNT(*) FROM users u LEFT JOIN companies c ON c.id=u.company_id
        WHERE u.company_id IS NOT NULL AND c.id IS NULL)                              AS ic08,
       (SELECT COUNT(*) FROM ai_player_scores
        WHERE score < 0 OR score > 100)                                               AS ic14;

-- ============================================================================
-- VARIANTE SQLite
-- ============================================================================
-- Reemplazar INTERVAL por datetime() en IC-20 y IC-23:
--   pv.created_at > datetime(adl.created_at, '+1 hour')
--   expires_at > datetime('now', '-30 days')
--
-- LOWER(name) es portable.
-- Las queries de COUNT/HAVING son idénticas.
