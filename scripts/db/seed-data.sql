-- ============================================================================
-- Argus Projects — Pack 48-H Round 3 · #101
-- seed-data.sql
-- ----------------------------------------------------------------------------
-- Datos mínimos para que un developer levante el stack y vea data en el panel.
-- Idempotente (ON CONFLICT DO NOTHING) — re-correr sin miedo.
--
-- ⚠️  NO ejecutar en producción.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1 · Empresa
-- ---------------------------------------------------------------------------
INSERT INTO companies (id, name, slug, created_at, plan)
VALUES (1, 'Dev Tenant', 'dev-tenant', NOW(), 'pro')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 2 · Usuarios
--   admin@dev.local / dev123 (hash bcrypt placeholder; reemplazar con real)
-- ---------------------------------------------------------------------------
INSERT INTO users (id, company_id, email, password_hash, role, is_active, created_at)
VALUES
    (1, 1, 'admin@dev.local',  '$2b$12$DEVHASH_ADMIN_REPLACE_ME', 'admin',  TRUE, NOW()),
    (2, 1, 'staff1@dev.local', '$2b$12$DEVHASH_STAFF_REPLACE_ME', 'staff',  TRUE, NOW()),
    (3, 1, 'staff2@dev.local', '$2b$12$DEVHASH_STAFF_REPLACE_ME', 'staff',  TRUE, NOW()),
    (4, 1, 'viewer@dev.local', '$2b$12$DEVHASH_VIEW_REPLACE_ME',  'viewer', TRUE, NOW()),
    (5, 1, 'apiuser@dev.local','$2b$12$DEVHASH_API_REPLACE_ME',   'api',    TRUE, NOW())
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3 · Plugin keys
-- ---------------------------------------------------------------------------
INSERT INTO company_plugin_keys (id, company_id, key_value, server_name, created_at, is_active)
VALUES (1, 1, 'dev-plugin-key-1234567890', 'dev-server-1', NOW(), TRUE)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 4 · Scan tokens (10 tokens; algunos consumidos, otros no)
-- ---------------------------------------------------------------------------
INSERT INTO scan_tokens (id, company_id, plugin_key_id, token, minecraft_username,
                         created_at, expires_at, used_at)
SELECT
    g, 1, 1,
    'tok-' || substr(md5(g::text), 1, 24),
    'Player_' || g,
    NOW() - (g || ' minutes')::interval,
    NOW() + INTERVAL '1 hour',
    CASE WHEN g % 3 = 0 THEN NOW() - ((g-1) || ' minutes')::interval END
FROM generate_series(1, 10) AS g
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 5 · Scans (100 scans, mezcla de verdicts)
-- ---------------------------------------------------------------------------
INSERT INTO scans (id, token_id, machine_id, minecraft_username, started_at,
                   completed_at, status, verdict, risk_score)
SELECT
    g,
    ((g - 1) % 10) + 1,                                       -- distribuye sobre los 10 tokens
    md5(g::text || 'machine'),
    'Player_' || (((g - 1) % 10) + 1),
    NOW() - (g || ' minutes')::interval,
    NOW() - (g || ' minutes')::interval + INTERVAL '30 seconds',
    CASE WHEN g % 11 = 0 THEN 'error'
         WHEN g %  7 = 0 THEN 'in_progress'
         ELSE 'completed' END,
    CASE WHEN g %  5 = 0 THEN 'ban'
         WHEN g %  3 = 0 THEN 'suspicious'
         WHEN g % 11 = 0 THEN NULL
         ELSE 'clean' END,
    (random() * 100)::numeric(6,2)
FROM generate_series(1, 100) AS g
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 6 · Plugin violations (200 violations)
-- ---------------------------------------------------------------------------
INSERT INTO plugin_violations (id, scan_id, violation_type, severity, detected_at, details)
SELECT
    g,
    ((g - 1) % 100) + 1,
    (ARRAY['fly','speed','reach','killaura','xray','badpkt'])[1 + (g % 6)],
    (ARRAY['low','medium','high','critical'])[1 + (g % 4)],
    NOW() - (g || ' minutes')::interval,
    jsonb_build_object('seed', TRUE, 'pkt', g)
FROM generate_series(1, 200) AS g
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- 7 · Sequences setval (para evitar colisiones en futuros inserts)
-- ---------------------------------------------------------------------------
SELECT setval(pg_get_serial_sequence('companies','id'), (SELECT COALESCE(MAX(id),1) FROM companies));
SELECT setval(pg_get_serial_sequence('users','id'),     (SELECT COALESCE(MAX(id),1) FROM users));
SELECT setval(pg_get_serial_sequence('scans','id'),     (SELECT COALESCE(MAX(id),1) FROM scans));
SELECT setval(pg_get_serial_sequence('scan_tokens','id'), (SELECT COALESCE(MAX(id),1) FROM scan_tokens));
SELECT setval(pg_get_serial_sequence('plugin_violations','id'), (SELECT COALESCE(MAX(id),1) FROM plugin_violations));
SELECT setval(pg_get_serial_sequence('company_plugin_keys','id'), (SELECT COALESCE(MAX(id),1) FROM company_plugin_keys));

COMMIT;

-- ---------------------------------------------------------------------------
-- Verificación
-- ---------------------------------------------------------------------------
SELECT 'companies' AS t, COUNT(*) FROM companies
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'scans', COUNT(*) FROM scans
UNION ALL SELECT 'scan_tokens', COUNT(*) FROM scan_tokens
UNION ALL SELECT 'plugin_violations', COUNT(*) FROM plugin_violations
UNION ALL SELECT 'company_plugin_keys', COUNT(*) FROM company_plugin_keys;
