-- ============================================================================
-- Argus Projects — Pack 48-H Round 3 · #103
-- golden-schema.sql
-- ----------------------------------------------------------------------------
-- "Golden" schema reference para tablas críticas. Sirve como entrada a:
--   - schema-drift-check.py (compara contra prod)
--   - tests CI (test_schema_golden.py)
--
-- Filosofía: este archivo NO crea data ni cambia tablas. Sólo describe lo que
-- esperamos ver cuando dumpemos el schema. Se mantiene a mano (por ahora) tras
-- cada migration aprobada; en el futuro se generará automático desde Alembic.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Cómo generar el dump "actual" (para diff manual):
-- ---------------------------------------------------------------------------
-- $ pg_dump --schema-only --no-owner --no-acl --no-comments --dbname=$DATABASE_URL \
--           > /tmp/actual_schema.sql
-- $ diff -u scripts/db/golden-schema.sql /tmp/actual_schema.sql | less
-- ---------------------------------------------------------------------------

-- Las siguientes secciones documentan el shape esperado en formato
-- "CREATE TABLE IF NOT EXISTS" (idempotente). Tipos canonical-form para que
-- el diff sea estable.

-- ===========================================================================
-- companies
-- ===========================================================================
CREATE TABLE IF NOT EXISTS companies (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(120) NOT NULL UNIQUE,
    plan        VARCHAR(32)  NOT NULL DEFAULT 'free',
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_companies_slug ON companies (slug);

-- ===========================================================================
-- users
-- ===========================================================================
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(32)  NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    last_ip         VARCHAR(64),
    last_login_at   TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, email)
);
CREATE INDEX IF NOT EXISTS idx_users_company ON users (company_id);
CREATE INDEX IF NOT EXISTS idx_users_email   ON users (email);

-- ===========================================================================
-- scan_tokens
-- ===========================================================================
CREATE TABLE IF NOT EXISTS scan_tokens (
    id                  SERIAL PRIMARY KEY,
    company_id          INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    plugin_key_id       INTEGER REFERENCES company_plugin_keys(id) ON DELETE SET NULL,
    token               VARCHAR(64)  NOT NULL UNIQUE,
    minecraft_username  VARCHAR(64),
    created_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    expires_at          TIMESTAMP    NOT NULL,
    used_at             TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_scan_tokens_company  ON scan_tokens (company_id);
CREATE INDEX IF NOT EXISTS idx_scan_tokens_expires  ON scan_tokens (expires_at);

-- ===========================================================================
-- scans  (target post-F-001 incluye company_id)
-- ===========================================================================
CREATE TABLE IF NOT EXISTS scans (
    id                  BIGSERIAL PRIMARY KEY,
    token_id            INTEGER REFERENCES scan_tokens(id) ON DELETE SET NULL,
    company_id          INTEGER REFERENCES companies(id) ON DELETE CASCADE,  -- F-001
    machine_id          VARCHAR(128),
    minecraft_username  VARCHAR(64),
    started_at          TIMESTAMP    NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMP,
    status              VARCHAR(32)  NOT NULL DEFAULT 'in_progress',
    verdict             VARCHAR(32),
    risk_score          NUMERIC(6,2)
);
CREATE INDEX IF NOT EXISTS idx_scans_token        ON scans (token_id);
CREATE INDEX IF NOT EXISTS idx_scans_company_time ON scans (company_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_status       ON scans (status);

-- ===========================================================================
-- plugin_violations
-- ===========================================================================
CREATE TABLE IF NOT EXISTS plugin_violations (
    id              BIGSERIAL PRIMARY KEY,
    scan_id         BIGINT REFERENCES scans(id) ON DELETE CASCADE,
    violation_type  VARCHAR(64) NOT NULL,
    severity        VARCHAR(32) NOT NULL,
    detected_at     TIMESTAMP   NOT NULL DEFAULT NOW(),
    details         JSONB
);
CREATE INDEX IF NOT EXISTS idx_pv_scan ON plugin_violations (scan_id);
CREATE INDEX IF NOT EXISTS idx_pv_type ON plugin_violations (violation_type);

-- ===========================================================================
-- ai_decisions_log
-- ===========================================================================
CREATE TABLE IF NOT EXISTS ai_decisions_log (
    id              BIGSERIAL PRIMARY KEY,
    company_id      INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    scan_id         BIGINT REFERENCES scans(id) ON DELETE SET NULL,
    player_uuid     UUID,
    verdict         VARCHAR(32)  NOT NULL,
    confidence_score NUMERIC(6,2),
    model_version   VARCHAR(64),
    created_at      TIMESTAMP    NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_adl_company_created ON ai_decisions_log (company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_adl_player          ON ai_decisions_log (player_uuid);

-- ===========================================================================
-- staff_audit_log
-- ===========================================================================
CREATE TABLE IF NOT EXISTS staff_audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    company_id  INTEGER REFERENCES companies(id) ON DELETE CASCADE,
    action      VARCHAR(128) NOT NULL,
    target_type VARCHAR(64),
    target_id   VARCHAR(64),
    meta        JSONB,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sal_user_action ON staff_audit_log (user_id, action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sal_company_action ON staff_audit_log (company_id, action, created_at DESC);

-- ===========================================================================
-- (Resto de tablas: ver schema-pack48.md)
-- Mantener este archivo sincronizado con el schema "esperado" post-migrations.
-- ===========================================================================
