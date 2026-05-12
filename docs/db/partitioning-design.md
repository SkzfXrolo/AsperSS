# Argus Projects — Partitioning design (Pack 48-H Round 3 · #89)

## Objetivo

Reducir el costo (IO, VACUUM, retention) de las tres tablas de **mayor crecimiento** introduciendo particiones declarativas de PostgreSQL (PG10+, recomendado PG14+).

| Tabla | Columna de partición | Estrategia | Granularidad | Justificación |
| --- | --- | --- | --- | --- |
| `scans` | `started_at` | RANGE | mensual | Queries casi siempre filtran rango temporal o "últimos 30/90 días"; retention via `DROP PARTITION` antes que `DELETE`. |
| `ai_decisions_log` | `created_at` | RANGE | semanal | Append-only de alto volumen; permite borrar 7d en un solo `DROP PARTITION`. |
| `staff_audit_log` | `created_at` | RANGE | trimestral | Volumen moderado, retención legal larga; trimestral evita exceso de particiones. |

> **No** particionar todavía: `scan_results`, `plugin_violations`. Primero hay que cubrir las tablas raíz; particionar tablas con FK hacia tablas no particionadas requiere cuidado (ver "Trade-offs").

## Beneficios esperados

1. **Planner**: queries por rango se reducen a una sola partición → menos páginas leídas.
2. **Retention**: `DROP TABLE scans_2025_05` reemplaza un `DELETE` de millones de filas (no genera bloat).
3. **Mantenimiento**: `VACUUM` y `REINDEX` por partición, en paralelo.
4. **Backups**: posibilidad de excluir particiones frías o archivarlas a S3.

## Trade-offs (riesgos reales)

| Tema | Riesgo | Mitigación |
| --- | --- | --- |
| **PK + columna de partición** | PG exige que la columna de partición esté en la PK / UNIQUE | Cambiar `PRIMARY KEY (id)` → `PRIMARY KEY (id, started_at)` |
| **FK desde otras tablas** | `scan_results.scan_id` → `scans.id` se complica si scans está particionada | Mantener FK pero **revalidar** post-migración; o convertir FK a "soft" referencial (riesgo: integridad débil) |
| **Inserts cross-partition** | Cliente inserta `started_at` futuro fuera de rangos creados | Default partition (`PARTITION default`) para que no falle |
| **Sequence global** | `id SERIAL` sigue funcionando (sequence compartida) | OK; vigilar reset en restore |
| **`pg_dump` parcial** | Backups por tabla deben enumerar particiones | Usar `--table=scans*` |
| **Pre-Pack 48 no tiene `company_id` en scans** (F-001) | Particionar antes del fix lock-in mal layout | Aplicar F-001 **primero**, luego particionar |
| **Render managed** | Render puede no permitir `pg_partman` extension | Verificar; alternativa: triggers de auto-create de particiones |

## Roadmap recomendado

1. **D-30:** F-001 aplicado (columna `scans.company_id` + backfill).
2. **D-15:** crear `pg_partman` (si disponible) o función custom `argus_create_monthly_partition()`.
3. **D-7:** migración en staging con clone de prod (volumen real).
4. **D:** ventana de aplicación con downtime declarado (≤30 min para conversión a partitioned root + attach).
5. **D+1..D+30:** observar planner (`pg_stat_user_tables` por partición).

## Naming convention

- `scans_2026_05` (YYYY_MM)
- `ai_decisions_log_2026w19` (ISO week)
- `staff_audit_log_2026q2`
- `partition_default` (catch-all)

## Política de retención por tabla

| Tabla | Particiones online | Particiones cold (S3 export) |
| --- | --- | --- |
| `scans` | últimas **24 meses** | después, export Parquet y `DROP` |
| `ai_decisions_log` | últimas **26 semanas** (6 meses) | export weekly post-cierre |
| `staff_audit_log` | últimos **8 trimestres** (2 años) | compliance review antes de drop |

Alineado con `cleanup-policy-pack48.sql` Round 1.

## Métricas a monitorear post-rollout

- Tiempo de planning vs ejecución (debería caer planning en rangos grandes).
- Cantidad de particiones (no superar ~1000 por tabla — overhead del planner sube).
- `pg_partman.part_config` (si se usa la extensión).
- `pg_stat_user_tables.idx_scan` por partición — detectar particiones "muertas" sin uso.
