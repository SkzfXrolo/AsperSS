# Argus DQ baseline (Pack 48-H Round 6 · #158)

## Estado inicial sugerido (Pack 49)

| KPI | Objetivo |
| --- | --- |
| DQ pass rate 7d | ≥ 99% checks core |
| Time-to-detect anomalía volume | < 1h |
| Time-to-fix DQ HIGH | < 24h |
| Backfill success rate | 100% scripts idempotentes |

## Tablas con DQ obligatorio Pack 49

- `scans`, `companies`, `users`, `ai_decisions_log`, `staff_audit_log`.

## Owner

Subagente H propone definiciones; ejecución por equipo Pack 49 DBA + dev.

## Referencias

- `docs/db/data-quality-framework/dq-checks-catalog.md`
