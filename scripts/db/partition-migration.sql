-- ============================================================================
-- Argus Projects — Pack 48-H Round 3 · #89
-- partition-migration.sql
-- ----------------------------------------------------------------------------
-- Migración de las tres tablas críticas a particiones declarativas.
--
-- ⚠️  NO ejecutar contra producción sin:
--   1) Backup completo previo (ver scripts/db/backup-automation.sh).
--   2) Ensayo en staging con clone de prod.
--   3) Confirmación de que columna scans.company_id ya existe (F-001).
--   4) Ventana de mantenimiento ≥30 min.
--
-- Estrategia general (sin downtime largo): create new partitioned root,
-- copy data via INSERT ... SELECT en batches, swap names.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- BLOQUE 1 · scans — RANGE mensual sobre started_at
-- ---------------------------------------------------------------------------

BEGIN;

-- Paso 1: nueva tabla raíz particionada (estructura espejo).
CREATE TABLE IF NOT EXISTS scans_p (
    LIKE scans INCLUDING ALL EXCLUDING CONSTRAINTS EXCLUDING INDEXES
) PARTITION BY RANGE (started_at);

-- Re-añadir constraints; PG exige started_at en la PK porque es el
-- partition key. La PK pasa de (id) a (id, started_at).
ALTER TABLE scans_p ADD PRIMARY KEY (id, started_at);

COMMIT;

-- Paso 2: particiones iniciales (ajustar fechas según producción).
-- Mantener 24 meses online + 1 default catch-all.
DO $$
DECLARE
    m DATE := date_trunc('month', CURRENT_DATE - INTERVAL '24 months')::date;
    next_m DATE;
    pname TEXT;
BEGIN
    WHILE m <= date_trunc('month', CURRENT_DATE + INTERVAL '1 month')::date LOOP
        next_m := (m + INTERVAL '1 month')::date;
        pname := 'scans_' || to_char(m, 'YYYY_MM');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF scans_p FOR VALUES FROM (%L) TO (%L)',
            pname, m, next_m
        );
        m := next_m;
    END LOOP;
END $$;

-- Default partition para inserts fuera de rango (errores de reloj o futuros).
CREATE TABLE IF NOT EXISTS scans_default PARTITION OF scans_p DEFAULT;

-- Paso 3: índices replicados en la raíz (PG14+ propaga a particiones).
CREATE INDEX IF NOT EXISTS idx_scans_p_token_id ON scans_p (token_id);
CREATE INDEX IF NOT EXISTS idx_scans_p_started_desc ON scans_p (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scans_p_machine_id ON scans_p (machine_id);
-- (Si F-001 aplicado:)
-- CREATE INDEX IF NOT EXISTS idx_scans_p_company_started ON scans_p (company_id, started_at DESC);

-- Paso 4: copiar datos en batches (no ejecutar en transacción única).
-- Para tablas <1M filas, un solo INSERT es aceptable.
-- Pseudocódigo del loop batched (no ejecutar tal cual; ajustar):

/*
DO $$
DECLARE
    cutoff TIMESTAMP := (SELECT MIN(started_at) FROM scans);
    step   INTERVAL  := INTERVAL '1 month';
    limit_top TIMESTAMP := CURRENT_TIMESTAMP + INTERVAL '1 day';
    inserted INT;
BEGIN
    WHILE cutoff < limit_top LOOP
        INSERT INTO scans_p SELECT * FROM scans
        WHERE started_at >= cutoff AND started_at < cutoff + step
        ON CONFLICT DO NOTHING;
        GET DIAGNOSTICS inserted = ROW_COUNT;
        RAISE NOTICE 'scans copy % rows for window starting %', inserted, cutoff;
        cutoff := cutoff + step;
        PERFORM pg_sleep(0.2);
    END LOOP;
END $$;
*/

-- Paso 5: swap nombres (downtime de segundos).
-- BEGIN;
--   ALTER TABLE scans RENAME TO scans_legacy_pre_partition;
--   ALTER TABLE scans_p RENAME TO scans;
-- COMMIT;

-- Paso 6: validación post-swap.
-- SELECT COUNT(*) FROM scans;            -- mismo orden de magnitud
-- SELECT relname FROM pg_inherits
--   JOIN pg_class c ON c.oid = inhrelid
--   WHERE inhparent = 'scans'::regclass;
-- (debe listar las N particiones creadas)

-- Paso 7: tras 7 días estables: DROP TABLE scans_legacy_pre_partition;

-- ---------------------------------------------------------------------------
-- BLOQUE 2 · ai_decisions_log — RANGE semanal sobre created_at
-- ---------------------------------------------------------------------------

BEGIN;
CREATE TABLE IF NOT EXISTS ai_decisions_log_p (
    LIKE ai_decisions_log INCLUDING ALL EXCLUDING CONSTRAINTS EXCLUDING INDEXES
) PARTITION BY RANGE (created_at);

ALTER TABLE ai_decisions_log_p ADD PRIMARY KEY (id, created_at);
COMMIT;

-- 26 semanas hacia atrás + 1 hacia adelante + default.
DO $$
DECLARE
    w DATE := (date_trunc('week', CURRENT_DATE - INTERVAL '26 weeks'))::date;
    nw DATE;
    pname TEXT;
BEGIN
    WHILE w <= date_trunc('week', CURRENT_DATE + INTERVAL '1 week')::date LOOP
        nw := (w + INTERVAL '7 days')::date;
        pname := 'ai_decisions_log_' || to_char(w, 'IYYY"w"IW');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF ai_decisions_log_p FOR VALUES FROM (%L) TO (%L)',
            pname, w, nw
        );
        w := nw;
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS ai_decisions_log_default PARTITION OF ai_decisions_log_p DEFAULT;

CREATE INDEX IF NOT EXISTS idx_adl_p_company ON ai_decisions_log_p (company_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_adl_p_player  ON ai_decisions_log_p (player_uuid, created_at DESC);

-- Copia + swap análogos al bloque 1 (comentado para evitar ejecución accidental).

-- ---------------------------------------------------------------------------
-- BLOQUE 3 · staff_audit_log — RANGE trimestral sobre created_at
-- ---------------------------------------------------------------------------

BEGIN;
CREATE TABLE IF NOT EXISTS staff_audit_log_p (
    LIKE staff_audit_log INCLUDING ALL EXCLUDING CONSTRAINTS EXCLUDING INDEXES
) PARTITION BY RANGE (created_at);

ALTER TABLE staff_audit_log_p ADD PRIMARY KEY (id, created_at);
COMMIT;

DO $$
DECLARE
    q DATE := date_trunc('quarter', CURRENT_DATE - INTERVAL '8 quarters')::date;
    nq DATE;
    pname TEXT;
BEGIN
    WHILE q <= date_trunc('quarter', CURRENT_DATE + INTERVAL '1 quarter')::date LOOP
        nq := (q + INTERVAL '3 months')::date;
        pname := 'staff_audit_log_' || to_char(q, 'YYYY"q"Q');
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF staff_audit_log_p FOR VALUES FROM (%L) TO (%L)',
            pname, q, nq
        );
        q := nq;
    END LOOP;
END $$;

CREATE TABLE IF NOT EXISTS staff_audit_log_default PARTITION OF staff_audit_log_p DEFAULT;

CREATE INDEX IF NOT EXISTS idx_sal_p_user_action ON staff_audit_log_p (user_id, action, created_at DESC);

-- ---------------------------------------------------------------------------
-- HELPER · mantenimiento automático mensual
-- ---------------------------------------------------------------------------
-- Ejecutar via pg_cron o cron externo: precrea partición del siguiente periodo
-- y borra las muy viejas. Pseudocódigo para adaptar.

/*
CREATE OR REPLACE FUNCTION argus_rotate_partitions() RETURNS void AS $$
DECLARE
    next_month_start DATE := date_trunc('month', CURRENT_DATE + INTERVAL '1 month');
    drop_before     DATE := CURRENT_DATE - INTERVAL '24 months';
    pname TEXT;
BEGIN
    -- precrear próxima partición scans
    pname := 'scans_' || to_char(next_month_start, 'YYYY_MM');
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF scans FOR VALUES FROM (%L) TO (%L)',
        pname, next_month_start, next_month_start + INTERVAL '1 month'
    );

    -- drop particiones >24m (revisar export Parquet antes)
    FOR pname IN SELECT relname FROM pg_class WHERE relname ~ '^scans_\d{4}_\d{2}$'
    LOOP
        -- compute window from name; SAFE: enumerar manualmente al inicio
        NULL;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
*/

-- ============================================================================
-- FIN — ver docs/db/partitioning-design.md para racional y trade-offs.
-- ============================================================================
