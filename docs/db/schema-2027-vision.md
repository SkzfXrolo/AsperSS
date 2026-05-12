# Argus Projects — Schema visión 12 meses (2027) — Pack 48-H Round 2

## Principios

1. **Una sola verdad** para key-value (`app_meta` + `app_settings` + `configurations` → `app_kv`).
2. **Migraciones versionadas** (Alembic) — cero DDL en `app.py` boot.
3. **company_id NOT NULL** en todas las tablas tenant-scoped (`scans`, `scan_results` vía backfill o denormalización controlada).
4. **Naming** de índices globalmente únicos: `idx_<table>_<cols>`.

## Consolidación de tablas

| Hoy | 2027 |
| --- | --- |
| `auto_labels` + `ai_auto_labels` | `ml_labels` unificada (`subject_type` = scan \| decision) |
| `hack_hashes` + `hack_blacklist` | `hash_intel` con `source` enum |
| `app_settings` | absorbido por `app_kv` |

## Normalización fixes

- `download_links.created_by` → siempre `VARCHAR` + opcional FK a `users.id` como string-free.
- `staff_feedback.verified_by` → `INTEGER` FK a `users.id` (migration cuidadosa).

## Deprecation plan

| Componente | Deprecar | Remover |
| --- | --- | --- |
| DDL en `init_db_async` | Q1 2027 | Q3 2027 |
| Queries `DATE(started_at)` | inmediato | reemplazo rango |
| Tablas legacy `scan_verdicts` / `empresas` (si existían en código muerto) | audit grep | siguiente cleanup PR |

## Particionado

- `scans`, `scan_results`, `plugin_violations`, `ai_decisions_log` → partición mensual automática.

## Seguridad

- Column-level encryption para `users.email` + `push_subscriptions`.
- `sslmode=verify-full` en prod.

## Observabilidad

- `pg_stat_statements` + Grafana obligatorio.
- SLO: p95 API read < 150ms, error rate < 0.1%.

## Equipo

- Rol **DBA rotativo** 1 semana/mes ejecuta `dr-drill-plan.md`.
