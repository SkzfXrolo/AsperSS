-- scripts/db/toolkits/pg_bloat_check.sql · Pack 48-H Round 6 · #159
-- Estimación de bloat por dead tuples (rápido, sin extensiones).
-- Para bloat preciso usar pgstattuple (privilegios).

SELECT schemaname, relname,
       n_live_tup, n_dead_tup,
       CASE WHEN (n_live_tup + n_dead_tup) > 0
            THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
            ELSE 0 END AS dead_pct,
       pg_size_pretty(pg_total_relation_size(schemaname || '.' || relname)) AS total_size,
       last_autovacuum, last_vacuum
FROM pg_stat_user_tables
WHERE n_live_tup + n_dead_tup > 1000
ORDER BY dead_pct DESC, n_dead_tup DESC
LIMIT 30;
