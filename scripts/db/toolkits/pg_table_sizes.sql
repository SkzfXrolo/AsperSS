-- scripts/db/toolkits/pg_table_sizes.sql · Pack 48-H Round 6 · #159
-- Top tablas por tamaño total (heap + toast + indexes).

SELECT n.nspname AS schema,
       c.relname AS name,
       pg_size_pretty(pg_relation_size(c.oid))            AS heap,
       pg_size_pretty(pg_indexes_size(c.oid))             AS indexes,
       pg_size_pretty(pg_table_size(c.oid))               AS heap_plus_toast,
       pg_size_pretty(pg_total_relation_size(c.oid))      AS total
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r','p')
  AND n.nspname NOT IN ('pg_catalog','information_schema')
ORDER BY pg_total_relation_size(c.oid) DESC
LIMIT 30;
