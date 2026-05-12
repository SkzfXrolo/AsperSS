# Scan storage optimization (Pack 48-H Round 5 · #147)

## Problema

`scans` es la tabla de mayor crecimiento: almacenamiento, índices, autovacuum, backups.

## Estrategias

| Estrategia | Impacto |
| --- | --- |
| Partitioning mensual | retención por DROP partition (`partitioning-design.md`) |
| Archivo JSONB pesado | mover detalles a `scan_artifacts` tabla o S3 object + pointer |
| BRIN en `created_at` | reduce index size append-only |
| Compresión TOAST | revisar columnas grandes repetidas |
| Column pruning | eliminar columnas legacy no usadas (migration) |

## Normalización payloads

- Mantener en row sólo campos query-hot; offload cold fields.

## Métricas

- `pg_total_relation_size('scans')` weekly.
- Ratio toast vs heap.

## Referencias

- `docs/db/argus-scenarios/violation-aggregation.md`
