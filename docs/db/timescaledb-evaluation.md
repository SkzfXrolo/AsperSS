# TimescaleDB evaluation (Pack 48-H Round 3 · #94)

## TL;DR

**Recomendación: NO migrar a TimescaleDB ahora.** Postgres "vanilla" + partitioning declarativo (#89) + MVs (#90) cubre el 90% del beneficio sin el costo de mudanza ni de lock-in. Re-evaluar cuando:

- DB > 100 GB de datos time-series, **o**
- Necesitemos continuous aggregates con latencia <1 min, **o**
- Compresión de columnas (≥10×) sea económicamente significativa.

## Tablas candidatas

| Tabla | Tipo de carga | TimescaleDB ROI |
| --- | --- | --- |
| `scans` | mixed (insert + lookups por PK + range queries) | medio |
| `ai_decisions_log` | append-only, time-range | **alto** |
| `plugin_violations` | append-only, time-range | medio |
| `staff_audit_log` | append-only, baja frecuencia | bajo |
| `companies`, `users`, `ai_player_profiles` | OLTP relacional | nulo |

## Beneficios reales de hypertables vs. partitioning manual

| Feature | TimescaleDB | PG vanilla particionado |
| --- | --- | --- |
| Chunk creation automático | ✅ | ⚠️ requiere cron + función custom |
| Compression nativa (10×) | ✅ | ❌ (sólo `TOAST` por fila) |
| Continuous aggregates (refresh incremental) | ✅ | ❌ (refresh full MV) |
| Retention policy declarativa | `add_retention_policy()` | `DROP TABLE` manual |
| Query planner mejorado (chunk exclusion) | ✅ | parcial (constraint exclusion) |
| Compatibilidad con extensiones PG | mayoría | total |
| Costo licencia | Apache-2 (community) + Enterprise (compresión avanzada, multinode) | gratis |

## Continuous aggregates vs MVs

- MV (`mv_daily_scan_stats`): `REFRESH MATERIALIZED VIEW CONCURRENTLY` recalcula **todo** cada 5 min → cost grows con tamaño total.
- Continuous aggregate (Timescale): mantiene la agregación incremental on-the-fly + refresh policy → cost grows sólo con datos nuevos.

Para `scans`/`ai_decisions_log`, a partir de >10M filas, esto se nota.

## Migration cost

| Tema | Costo |
| --- | --- |
| Render PG managed sin Timescale | **bloqueante**: Render no soporta extensions custom → tendríamos que self-host. |
| Self-host PG con Timescale | infra extra: VM, backups, monitoring, security patching. |
| Re-ingest de datos | `SELECT create_hypertable('scans', 'started_at', migrate_data => TRUE)` migra in-place; ~1h por 100M filas. |
| App code | mayormente transparente (Timescale es una extensión PG); algunas queries pueden requerir hints. |
| Compatibilidad ORM | SQLAlchemy 100%; pgvector y pgcrypto siguen funcionando. |

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| Lock-in: cambiar de proveedor exige re-export. | Mantener export Parquet via `dw-export.sql`. |
| Compresión rompe DDL: no se puede `ALTER TABLE` chunk comprimido. | Descomprimir antes de migraciones. |
| Continuous aggregates exigen `time_bucket` (no `date_trunc`) → rewrite SQL. | Mantener views con `date_trunc` para compat. |
| Versiones major upgrades requieren ventana. | Igual que PG vanilla. |

## Cuándo SÍ migrar (gates de decisión)

1. **Volumen**: `pg_total_relation_size('ai_decisions_log') > 50GB`.
2. **Costo storage**: Render PG storage cost > 2× lo que costaría DB self-host con compresión.
3. **Latencia de dashboards**: p95 dashboards > 2s sostenido tras MVs.
4. **Equipo**: contamos con un eng dedicado a DB ops.

## Alternativas si elegimos NO migrar

- ClickHouse externo para analytics (mejor compresión y query, pero schema separado).
- DuckDB embedded para reportes batch (cero infra).
- Citus (sharding nativo PG) si el problema es throughput de writes (≠ time-series).

## Decisión

**Pack 48: NO migrar.** Mantener Render PG + partitioning + MVs.
**Reevaluación: Pack 60+** (revisar al cierre de Q3 2026 con métricas reales de volumen).
