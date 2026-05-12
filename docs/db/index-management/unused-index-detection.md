# Unused index detection (Pack 48-H Round 6 · #155)

## Por qué

Índices sin uso ocupan disco, ralentizan writes, contaminan plan caches.

## Query

```sql
SELECT s.schemaname, s.relname AS table, s.indexrelname AS index,
       s.idx_scan, pg_size_pretty(pg_relation_size(s.indexrelid)) AS size
FROM pg_stat_user_indexes s
JOIN pg_index i ON i.indexrelid = s.indexrelid
WHERE s.idx_scan = 0
  AND NOT i.indisunique
  AND NOT i.indisprimary
ORDER BY pg_relation_size(s.indexrelid) DESC;
```

## Reglas

- Esperar **al menos 7-30 días** después de cambios para concluir.
- Excluir PKs y UNIQUE constraints.
- Considerar uso esporádico (mensual reporting).

## Drop seguro

```sql
DROP INDEX CONCURRENTLY IF EXISTS idx_unused;
```

## Argus

Job mensual (`monitoring-queries.sql`) revisa candidatos → revisión humana antes de drop.

## Referencias

- `scripts/db/toolkits/pg_unused_indexes.sql`
