-- ============================================================================
-- Argus Projects — Pack 48-H Round 2
-- monitoring-queries.sql
-- ----------------------------------------------------------------------------
-- Top ~20 consultas para monitoreo continuo (Grafana / pgAdmin / cron).
-- Placeholders: {{database}} en Grafana PostgreSQL datasource.
-- ============================================================================

-- M1) Tamaño por tabla (top 25)
SELECT schemaname || '.' || relname AS table_name,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       n_live_tup AS est_rows
FROM   pg_stat_user_tables
ORDER  BY pg_total_relation_size(relid) DESC
LIMIT  25;

-- M2) Índices nunca usados (candidatos a DROP tras 14d observación)
SELECT indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS idx_size
FROM   pg_stat_user_indexes
WHERE  idx_scan = 0 AND indexrelname NOT LIKE 'pg_toast%'
ORDER  BY pg_relation_size(indexrelid) DESC
LIMIT  50;

-- M3) Índices más leídos (hot)
SELECT indexrelname, idx_scan, idx_tup_fetch
FROM   pg_stat_user_indexes
ORDER  BY idx_scan DESC NULLS LAST
LIMIT  20;

-- M4) Seq scans más costosos en tablas grandes
SELECT relname, seq_scan, seq_tup_read, idx_scan
FROM   pg_stat_user_tables
WHERE  seq_scan > 0
ORDER  BY seq_tup_read DESC
LIMIT  20;

-- M5) Dead tuples ratio (bloat señal)
SELECT relname, n_live_tup, n_dead_tup,
       round(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS dead_pct
FROM   pg_stat_user_tables
WHERE  n_live_tup + n_dead_tup > 10000
ORDER  BY dead_pct DESC NULLS LAST
LIMIT  20;

-- M6) Conexiones actuales vs max
SELECT count(*) AS connections,
       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max_conn
FROM   pg_stat_activity;

-- M7) Queries activas (no idle)
SELECT pid, usename, state, wait_event_type, wait_event,
       left(query, 120) AS query_preview,
       now() - query_start AS running_for
FROM   pg_stat_activity
WHERE  state <> 'idle'
ORDER  BY query_start;

-- M8) Bloqueos: quién bloquea a quién
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_query
FROM   pg_catalog.pg_locks blocked_locks
JOIN   pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN   pg_catalog.pg_locks blocking_locks
       ON blocking_locks.locktype = blocked_locks.locktype
      AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
      AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
      AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
      AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
      AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
      AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
      AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
      AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
      AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
      AND blocking_locks.pid <> blocked_locks.pid
JOIN   pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE  NOT blocked_locks.granted;

-- M9) Replication lag (primario; si hay replica)
SELECT application_name, state, sync_state,
       write_lag, flush_lag, replay_lag
FROM   pg_stat_replication;

-- M10) Checkpointer / bgwriter (IO pressure)
SELECT * FROM pg_stat_bgwriter;

-- M11) Cache hit ratio (shared_buffers)
SELECT sum(heap_blks_read) AS heap_read,
       sum(heap_blks_hit)  AS heap_hit,
       round(100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) AS cache_hit_pct
FROM   pg_statio_user_tables;

-- M12) Top table I/O (PG16+ pg_stat_io — omitir si la vista no existe)
-- SELECT * FROM pg_stat_io;
SELECT 'skipped_pg_stat_io'::text AS m12_note;

-- M13) Long running transactions (> 5 min)
SELECT pid, now() - xact_start AS xact_age, left(query, 200)
FROM   pg_stat_activity
WHERE  xact_start IS NOT NULL AND now() - xact_start > interval '5 minutes';

-- M14) Autovacuum backlog
SELECT relname, last_autovacuum, last_autoanalyze, n_dead_tup
FROM   pg_stat_user_tables
WHERE  n_dead_tup > 50000
ORDER  BY n_dead_tup DESC
LIMIT  20;

-- M15) Invalid indexes (post CREATE INDEX CONCURRENTLY failure)
SELECT c.relname AS index_name
FROM   pg_class c
JOIN   pg_index i ON i.indexrelid = c.oid
WHERE  c.relkind = 'I' AND NOT i.indisvalid;

-- M16) Foreign keys sin índice en lado hijo (PG15 pg_constraint helper pattern)
SELECT conname, conrelid::regclass AS table_from
FROM   pg_constraint
WHERE  contype = 'f';

-- M17) Settings críticos
SELECT name, setting, unit, short_desc
FROM   pg_settings
WHERE  name IN ('shared_buffers','work_mem','maintenance_work_mem','max_connections','random_page_cost');

-- M18) Database size total
SELECT pg_size_pretty(pg_database_size(current_database()));

-- M19) Grafana placeholder — alert: dead_pct > 30 on scans
-- Panel query: reuse M5 filtered WHERE relname = 'scans'

-- M20) Statement timeout check (session)
SHOW statement_timeout;
