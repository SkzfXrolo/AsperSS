# Partition pruning (Pack 48-H Round 6 · #152)

## Qué es

El planner descarta particiones cuyo rango/lista/hash **no puede contener** filas que satisfagan el predicate.

## Cuándo pasa

- Constantes en `WHERE`: `WHERE created_at >= '2026-05-01'`.
- `enable_partition_pruning = on` (default).
- Plan-time pruning + run-time pruning (parámetros `$1`).

## Cómo verificar

```sql
EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM scans WHERE created_at >= now() - interval '1 day';
```

Buscar `Subplans Removed: N` o sólo `Partitions: scans_2026_05`.

## Bloqueadores comunes

- Funciones que ocultan partition key: `WHERE date_trunc('day', created_at) = '...'` → reescribir con range.
- Cast implícito raro → forzar tipo.
- `OR` que mezcla otras columnas.

## Argus

- Panel `last 24h scans` debe pegar 1-2 particiones máx.
- Tests de regression: añadir `EXPLAIN` snapshots a CI (`testing/strategies.md`).

## Referencias

- `docs/db/performance/query-optimization.md`
