-- ============================================================================
-- Argus Projects — Pack 48-H Round 4 · #121
-- reports/compliance-report.sql
-- ----------------------------------------------------------------------------
-- Soporte a DSAR (Data Subject Access Request) y GDPR.
-- Devuelve TODA la información asociada a un user_id o minecraft_username.
-- Output destinado a humano (legal) y/o cliente.
-- Parámetros:
--   \set p_user_id 42
--   \set p_minecraft_username 'PlayerName'
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1 · Datos asociados al user_id (cuenta staff/admin)
-- ---------------------------------------------------------------------------
\set user_id COALESCE(:'p_user_id', '0')::int

SELECT
    'users' AS source_table,
    u.id, u.company_id, u.role,
    argus_truncate_email(u.email)      AS email_masked,
    u.last_login_at, u.created_at, u.is_active
FROM users u
WHERE u.id = (:'p_user_id')::int;

-- sessions
SELECT 'user_sessions' AS source_table,
       us.id, us.created_at, us.last_seen_at,
       argus_anonymize_ip(us.ip::inet) AS ip_anon
FROM user_sessions us
WHERE us.user_id = (:'p_user_id')::int;

-- staff_audit_log donde actuó
SELECT 'staff_audit_log_actions' AS source_table,
       sal.id, sal.action, sal.target_type, sal.target_id, sal.created_at
FROM staff_audit_log sal
WHERE sal.user_id = (:'p_user_id')::int
ORDER BY sal.created_at DESC
LIMIT 500;

-- ---------------------------------------------------------------------------
-- 2 · Datos asociados al minecraft_username (jugador)
-- ---------------------------------------------------------------------------
\set mc_user COALESCE(:'p_minecraft_username', '')

-- scans
SELECT 'scans' AS source_table,
       s.id, s.company_id, s.started_at, s.completed_at,
       s.status, s.verdict, s.risk_score,
       argus_hash_pii(s.machine_id::text, 'dsar') AS machine_id_hash
FROM scans s
WHERE argus_normalize_username(s.minecraft_username) = argus_normalize_username(:'p_minecraft_username')
ORDER BY s.started_at DESC
LIMIT 1000;

-- violations
SELECT 'plugin_violations' AS source_table,
       v.id, v.violation_type, v.severity, v.detected_at
FROM plugin_violations v
JOIN scans s ON s.id = v.scan_id
WHERE argus_normalize_username(s.minecraft_username) = argus_normalize_username(:'p_minecraft_username')
ORDER BY v.detected_at DESC
LIMIT 1000;

-- ai_decisions / profile
SELECT 'ai_decisions_log' AS source_table,
       d.id, d.company_id, d.verdict, d.confidence_score,
       d.model_version, d.created_at
FROM ai_decisions_log d
JOIN ai_player_profiles p ON p.player_uuid = d.player_uuid
WHERE argus_normalize_username(p.player_name) = argus_normalize_username(:'p_minecraft_username')
ORDER BY d.created_at DESC
LIMIT 500;

-- ban_history
SELECT 'ban_history' AS source_table,
       b.id, b.company_id, b.reason, b.created_at, b.expires_at
FROM ban_history b
JOIN ai_player_profiles p ON p.player_uuid = b.player_uuid
WHERE argus_normalize_username(p.player_name) = argus_normalize_username(:'p_minecraft_username');

-- ---------------------------------------------------------------------------
-- 3 · "Right to be forgotten" helper (NO ejecuta deletes; sólo preview)
-- ---------------------------------------------------------------------------
SELECT 'WILL_BE_DELETED_IF_RTBF_APPROVED' AS note,
       'See data-classification.md for retention exceptions (audit logs)' AS notes;
