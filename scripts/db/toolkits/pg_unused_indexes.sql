-- scripts/db/toolkits/pg_unused_indexes.sql · Pack 48-H Round 6 · #159
-- Índices con idx_scan = 0 (excluyendo PK/UNIQUE).

SELECT s.schemaname,
       s.relname    AS table,
       s.indexrelname AS index,
       pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size,
       s.idx_scan
FROM pg_stat_user_indexes s
JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE s.idx_scan = 0
  AND NOT i.indisunique
  AND NOT i.indisprimary
ORDER BY pg_relation_size(s.indexrelid) DESC;
