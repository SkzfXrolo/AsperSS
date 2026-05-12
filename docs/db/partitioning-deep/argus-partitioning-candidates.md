# Argus partitioning candidates (Pack 48-H Round 6 · #152)

Resumen ejecutivo: candidatos a particionar, prioridad, granularidad.

| Tabla | Vol estimado | Particionar por | Granularidad | Prioridad | Retención |
| --- | --- | --- | --- | --- | --- |
| `scans` | alto | RANGE `created_at` | mensual | P0 | 12 meses hot + archivo |
| `ai_decisions_log` | alto | RANGE `timestamp` | semanal | P0 | 6 meses hot + archivo |
| `staff_audit_log` | medio | RANGE `created_at` | trimestral | P1 | 5 años (legal) |
| `ban_history` | bajo-medio | sin particionar | — | P3 | indefinido (legal) |
| `violations` | medio-alto | RANGE `created_at` | mensual | P1 | 12 meses |
| `plugin_heartbeats` | bajo (rotativo) | RANGE `created_at` | semanal | P2 | 30 días |

## Pasos por tabla (resumen)

1. Crear tabla nueva particionada `..._new`.
2. Backfill con `INSERT ... SELECT` particionado por mes.
3. Switch nombres (downtime breve) o usar logical replication para zero-downtime.

Detalle ya en `scripts/db/partition-migration.sql` (Round 3).

## Pre-reqs

- F-001 cerrado (PK debe incluir `created_at`).
- Validar que **todas** las queries top usan `created_at` en `WHERE` → pruning efectivo.

## Referencias

- `docs/db/partitioning-design.md` (Round 3)
- `docs/db/argus-cookbook/scan-table-evolution.md`
