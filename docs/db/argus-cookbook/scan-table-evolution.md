# Scan table evolution (Pack 48-H Round 6 · #163)

## Estado hoy

- Tabla `scans` monolítica.
- Sin `company_id` formal (F-001).
- Crecimiento alto.

## Hitos propuestos

| Pack | Cambio |
| --- | --- |
| 49 | Add `company_id` + index + RLS preview |
| 50 | Partitioning RANGE mensual + backfill |
| 51 | Covering index panel queries |
| 52 | Archivo S3 particiones > 12m |
| 53 | MV `mv_daily_scan_stats` consolidada |

## Riesgos

- Locks largos: usar CONCURRENTLY + batches.
- Mismatch dev SQLite vs prod PG: tests staged.

## Referencias

- `docs/db/partitioning-deep/argus-partitioning-candidates.md`
- `docs/db/argus-scenarios/scan-storage-optimization.md`
