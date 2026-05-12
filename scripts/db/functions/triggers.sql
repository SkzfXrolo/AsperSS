-- ============================================================================
-- Argus Projects — Pack 48-H Round 4 · #120
-- functions/triggers.sql
-- ----------------------------------------------------------------------------
-- Triggers para audit log automation y mantenimiento de timestamps.
-- Filosofía: triggers livianos. No business logic ni HTTP calls.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Helper: tabla destino del audit (si no existe ya con otro shape)
-- ---------------------------------------------------------------------------
-- Reuso de staff_audit_log si tiene los campos; si no, una tabla generica:
CREATE TABLE IF NOT EXISTS audit_changelog (
    id           BIGSERIAL PRIMARY KEY,
    schema_name  TEXT,
    table_name   TEXT,
    operation    CHAR(1) NOT NULL,     -- I, U, D
    pk_value     TEXT,
    company_id   INTEGER,
    actor_role   TEXT,                 -- current_user
    app_user     TEXT,                 -- current_setting('app.user_id')
    diff         JSONB,                -- columnas cambiadas
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_changelog_table_time
    ON audit_changelog (table_name, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_changelog_company
    ON audit_changelog (company_id, occurred_at DESC);

-- ---------------------------------------------------------------------------
-- 1 · trigger function · audit (insert/update/delete generic)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_audit_row()
RETURNS TRIGGER AS $$
DECLARE
    rec_pk    TEXT;
    rec_cid   INTEGER;
    diff_json JSONB := NULL;
BEGIN
    -- PK: convención id; ajustar caso a caso si la tabla tiene PK compuesta
    IF TG_OP = 'DELETE' THEN
        rec_pk := (row_to_json(OLD)->>'id');
        rec_cid := (row_to_json(OLD)->>'company_id')::int;
    ELSE
        rec_pk := (row_to_json(NEW)->>'id');
        rec_cid := (row_to_json(NEW)->>'company_id')::int;
    END IF;

    IF TG_OP = 'UPDATE' THEN
        SELECT jsonb_object_agg(key, jsonb_build_array(o.value, n.value))
        INTO diff_json
        FROM jsonb_each(row_to_json(OLD)::jsonb) o
        JOIN jsonb_each(row_to_json(NEW)::jsonb) n USING (key)
        WHERE o.value IS DISTINCT FROM n.value;
    END IF;

    INSERT INTO audit_changelog (schema_name, table_name, operation, pk_value, company_id,
                                 actor_role, app_user, diff)
    VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, LEFT(TG_OP, 1), rec_pk, rec_cid,
            current_user, current_setting('app.user_id', true), diff_json);

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------------
-- 2 · attach a tablas críticas (creación idempotente)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users', 'companies', 'company_plugin_keys',
        'ban_history', 'ai_model_versions'
    ] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%I ON %I', t, t);
        EXECUTE format(
            'CREATE TRIGGER trg_audit_%I
             AFTER INSERT OR UPDATE OR DELETE ON %I
             FOR EACH ROW EXECUTE FUNCTION argus_audit_row()',
            t, t
        );
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 3 · trigger · mantener updated_at coherente
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'companies', 'users', 'ai_player_profiles', 'plugin_servers'
    ] LOOP
        -- sólo si la tabla tiene columna updated_at
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = t AND column_name='updated_at'
        ) THEN
            EXECUTE format('DROP TRIGGER IF EXISTS trg_touch_%I ON %I', t, t);
            EXECUTE format(
                'CREATE TRIGGER trg_touch_%I
                 BEFORE UPDATE ON %I
                 FOR EACH ROW EXECUTE FUNCTION argus_touch_updated_at()',
                t, t
            );
        END IF;
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 4 · trigger · validación post-F-001: scans.company_id debe coincidir con token
-- ---------------------------------------------------------------------------
-- Comentado: depende de F-001 (scans.company_id column existente).
/*
CREATE OR REPLACE FUNCTION argus_scans_tenant_consistency()
RETURNS TRIGGER AS $$
DECLARE
    token_company INTEGER;
BEGIN
    IF NEW.token_id IS NOT NULL THEN
        SELECT company_id INTO token_company FROM scan_tokens WHERE id = NEW.token_id;
        IF token_company IS NOT NULL AND NEW.company_id IS NOT NULL
           AND token_company <> NEW.company_id THEN
            RAISE EXCEPTION 'scans.company_id (%) does not match scan_tokens.company_id (%)',
                NEW.company_id, token_company;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_scans_tenant_consistency ON scans;
CREATE TRIGGER trg_scans_tenant_consistency
BEFORE INSERT OR UPDATE OF company_id, token_id ON scans
FOR EACH ROW EXECUTE FUNCTION argus_scans_tenant_consistency();
*/

-- ---------------------------------------------------------------------------
-- 5 · trigger · NOTIFY al insertar scans (para CDC ligero, ver cdc-design.md)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION argus_notify_change()
RETURNS TRIGGER AS $$
DECLARE
    payload TEXT;
BEGIN
    -- payload pequeño (LIMIT 8KB por NOTIFY)
    payload := json_build_object(
        'op',     LEFT(TG_OP, 1),
        'table',  TG_TABLE_NAME,
        'id',     COALESCE(NEW, OLD)->>'id',
        'company_id', COALESCE(NEW, OLD)->>'company_id',
        'ts',     extract(epoch from NOW())
    )::text;
    PERFORM pg_notify('argus_changes', payload);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- Activar selectivamente (NO para tablas de logs append-only de alto volumen):
-- DROP TRIGGER IF EXISTS trg_notify_companies ON companies;
-- CREATE TRIGGER trg_notify_companies AFTER INSERT OR UPDATE OR DELETE ON companies
--     FOR EACH ROW EXECUTE FUNCTION argus_notify_change();

-- ============================================================================
-- FIN — ver stored-procedures-vs-app.md (#119) y cdc-design.md (#92).
-- ============================================================================
