-- ============================================================================
-- Argus Projects — Pack 48-H Round 4 · #114
-- bloat-check.sql
-- ----------------------------------------------------------------------------
-- Reportes de bloat de tablas e índices. Dos niveles:
--   1) Estimación barata (siempre disponible).
--   2) Precisión exacta (requiere extension pgstattuple).
--
-- ⚠️  En tablas grandes (>10GB), pgstattuple lee TODO. Correr en off-peak
--     o en read replica.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1 · Bloat de TABLAS (estimación basada en pg_stat_user_tables)
-- ---------------------------------------------------------------------------
SELECT
    schemaname,
    relname,
    n_live_tup,
    n_dead_tup,
    ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS pct_dead,
    pg_size_pretty(pg_total_relation_size(relid))                    AS total_size,
    pg_size_pretty(pg_table_size(relid))                             AS table_size,
    last_autovacuum,
    last_vacuum,
    n_mod_since_analyze
FROM pg_stat_user_tables
WHERE n_dead_tup > 100
ORDER BY pct_dead DESC NULLS LAST, n_dead_tup DESC
LIMIT 30;

-- ---------------------------------------------------------------------------
-- 2 · Bloat de TABLAS (precisión exacta vía pgstattuple)
--     Comentado por costo. Descomentar cuando sea necesario.
-- ---------------------------------------------------------------------------
-- CREATE EXTENSION IF NOT EXISTS pgstattuple;
-- SELECT
--     c.relname,
--     pg_size_pretty(pg_total_relation_size(c.oid))   AS total,
--     s.tuple_count, s.tuple_len, s.tuple_percent,
--     s.dead_tuple_count, s.dead_tuple_len, s.dead_tuple_percent,
--     s.free_space, s.free_percent
-- FROM pg_class c
-- JOIN pg_namespace n ON n.oid = c.relnamespace,
-- LATERAL pgstattuple(c.oid) s
-- WHERE c.relkind='r' AND n.nspname='public'
-- ORDER BY s.dead_tuple_percent DESC
-- LIMIT 10;

-- ---------------------------------------------------------------------------
-- 3 · Bloat de ÍNDICES (estimación basada en page count)
-- ---------------------------------------------------------------------------
SELECT
    schemaname,
    indexrelname,
    pg_size_pretty(pg_relation_size(indexrelid))    AS index_size,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE pg_relation_size(indexrelid) > 1024*1024            -- >1MB
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 30;

-- ---------------------------------------------------------------------------
-- 4 · Bloat de ÍNDICES (precisión exacta vía pgstatindex)
--     Costoso. Correr selectivamente.
-- ---------------------------------------------------------------------------
-- SELECT
--     i.indexrelname,
--     pg_size_pretty(pg_relation_size(i.indexrelid)) AS size,
--     s.version,
--     s.tree_level,
--     s.index_size,
--     s.root_block_no,
--     s.internal_pages,
--     s.leaf_pages,
--     s.empty_pages,
--     s.deleted_pages,
--     s.avg_leaf_density,
--     s.leaf_fragmentation
-- FROM pg_stat_user_indexes i,
--      LATERAL pgstatindex(i.indexrelid::regclass) s
-- WHERE i.idx_scan > 0
-- ORDER BY s.avg_leaf_density ASC
-- LIMIT 10;

-- ---------------------------------------------------------------------------
-- 5 · Resumen ejecutivo (una fila)
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                                 AS total_tables,
    COUNT(*) FILTER (WHERE n_dead_tup > 0)                   AS tables_with_dead,
    SUM(n_dead_tup)                                          AS total_dead_tuples,
    pg_size_pretty(SUM(pg_total_relation_size(relid)))       AS total_db_size,
    ROUND(AVG(NULLIF(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 0)), 2)
                                                              AS avg_pct_dead
FROM pg_stat_user_tables;

-- ---------------------------------------------------------------------------
-- 6 · Tablas con autovacuum lag (no se vacuumean hace tiempo)
-- ---------------------------------------------------------------------------
SELECT
    relname,
    n_dead_tup,
    last_autovacuum,
    NOW() - last_autovacuum                                AS since_last_av,
    last_vacuum,
    NOW() - last_vacuum                                    AS since_last_manual_v
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
  AND (last_autovacuum IS NULL OR last_autovacuum < NOW() - INTERVAL '7 days')
ORDER BY n_dead_tup DESC
LIMIT 20;

-- ---------------------------------------------------------------------------
-- 7 · Recomendaciones automáticas (heurísticas)
-- ---------------------------------------------------------------------------
SELECT
    relname,
    pct_dead,
    pg_size_pretty(size_bytes) AS size,
    CASE
        WHEN pct_dead < 20                          THEN 'OK'
        WHEN pct_dead < 40 AND size_bytes < 10737418240
                                                    THEN 'VACUUM (no urgent)'
        WHEN pct_dead < 40                          THEN 'VACUUM ANALYZE + monitor'
        WHEN size_bytes < 5368709120                THEN 'VACUUM FULL in window'
        ELSE                                             'pg_repack recommended'
    END AS recommendation
FROM (
    SELECT relname,
           ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS pct_dead,
           pg_total_relation_size(relid) AS size_bytes
    FROM pg_stat_user_tables
    WHERE n_dead_tup > 0
) sub
WHERE pct_dead >= 10
ORDER BY pct_dead DESC
LIMIT 30;

-- ============================================================================
-- FIN
-- ============================================================================
