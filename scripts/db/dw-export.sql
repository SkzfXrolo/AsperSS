-- ============================================================================
-- Argus Projects — Pack 48-H Round 2
-- dw-export.sql
-- ----------------------------------------------------------------------------
-- Plantillas COPY / vistas materializables para ETL hacia DW.
-- Ajustar anonimización antes de ejecutar en prod; preferir REPLICA read-only.
-- NO contiene credenciales.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Tabla de control de sync (crear en OLTP o en DW bridge DB)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dw_sync_state (
    sync_key   VARCHAR(64) PRIMARY KEY,
    last_ts    TIMESTAMPTZ NOT NULL DEFAULT 'epoch',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Vista: scans anonimizados para export
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_dw_scans_export AS
SELECT
    id,
    md5(COALESCE(machine_id::text, ''))       AS machine_id_hash,
    left(md5(lower(minecraft_username)), 12)   AS player_handle_token,
    started_at,
    completed_at,
    status,
    verdict,
    risk_score,
    -- company_id cuando exista en DDL post-F-001:
    NULL::INTEGER AS company_id_placeholder
FROM scans;

-- ---------------------------------------------------------------------------
-- Vista: violations export
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_dw_violations_export AS
SELECT
    id,
    company_id,
    md5(lower(player_uuid)) AS player_uuid_token,
    check_name,
    level,
    created_at
FROM plugin_violations;

-- ---------------------------------------------------------------------------
-- Ejemplo COPY (desde psql cliente, a stdout → gzip → S3)
-- \copy (SELECT * FROM v_dw_scans_export WHERE started_at > '2026-01-01') TO 'scans_partial.csv' CSV HEADER
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Incremental watermark pattern (ejemplo scans)
-- ---------------------------------------------------------------------------
-- SELECT MAX(started_at) FROM scans WHERE started_at > (SELECT last_ts FROM dw_sync_state WHERE sync_key='scans');

COMMENT ON VIEW v_dw_scans_export IS 'Pack48-H: anon export; reemplazar company_id_placeholder tras migración';
COMMENT ON VIEW v_dw_violations_export IS 'Pack48-H: PII tokenizado para DW';
