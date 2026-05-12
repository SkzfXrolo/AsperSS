# Argus Projects — ETL pipeline design (Pack 48-H Round 3 · #93)

## Modelo de capas

```
   ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
   │   RAW    │ ───► │ STAGING  │ ───► │ CLEANED  │ ───► │ AGGREGATED│
   └──────────┘      └──────────┘      └──────────┘      └──────────┘
   ingest 1:1      type-cast, dedup    business rules    metrics, MVs
   immutable       trustable           single source     fast dashboards
```

| Capa | Schema | Propósito | Frecuencia | Owner |
| --- | --- | --- | --- | --- |
| RAW | `raw_*` (vistas/tablas) | Snapshot fiel del origen (PG + plugin logs) | Hourly | Plataforma |
| STAGING | `stg_*` | Tipos normalizados, claves canónicas, NULL handling | Hourly | Plataforma |
| CLEANED | `cln_*` | Reglas de negocio, deduplicación, FK enforcement | Daily | Data |
| AGGREGATED | `agg_*` / `mv_*` | Agregaciones para dashboards | Real-time (MV) / Daily (agg) | Producto |

## Quality gates entre capas

| Origen → Destino | Test |
| --- | --- |
| RAW → STG | `count_rows_raw == count_rows_stg` (±0%) |
| STG → CLN | `cln.scan.company_id NOT NULL` (post-F-001) |
| STG → CLN | `cln.scan.player_uuid` formato UUID válido |
| CLN → AGG | `sum(agg.banned) <= sum(cln.scans)` |
| Cross-layer | `max(_loaded_at) < NOW() - 2h` → alerta de stale |

Cada gate vive en `scripts/db/etl-stages.sql` y se ejecuta como `assert_*` con `RAISE EXCEPTION` si falla.

## Origen de datos

| Fuente | Mecanismo | Cadencia |
| --- | --- | --- |
| Tablas OLTP | CDC slot (ver `cdc-design.md`) | continuous |
| Plugin logs (`/var/log/argus-plugin/*.json`) | rsync → S3 → ingest | hourly |
| Stripe / billing | API pull | daily |
| Sentry / errors | webhook | event-driven |

## Schedule

`pg_cron` o Airflow/dbt. Ejemplo:

```
*/15 * * * *  -- agg layer refresh (rápido)
0 * * * *     -- raw → staging consolidation
30 0 * * *    -- staging → cleaned (madrugada)
0 1 * * *     -- cleaned → aggregated full rebuild
```

## Idempotencia y reprocessing

- Toda tabla de capa tiene `_ingested_at TIMESTAMPTZ`, `_source TEXT`, `_pipeline_run_id UUID`.
- Reprocessing: `DELETE WHERE _pipeline_run_id = $1` luego rerun.
- Para evitar UPSERT race: usar `INSERT ... ON CONFLICT DO UPDATE` con `_pipeline_run_id` en `WHERE`.

## Quality dashboard

- `etl_runs` (id, started_at, finished_at, status, stage, rows_in, rows_out, error_msg).
- Grafana panel: éxito por capa por día, p95 duración.

## Trade-offs

| Tema | Pro | Contra |
| --- | --- | --- |
| 4 capas | Trazabilidad completa | Storage 2-3x mismas filas |
| MV final | Latencia <5min | Refresh cost |
| Reglas de negocio en SQL | Versionable, testeable | Difícil expresar lógica compleja → mover a Python |
| Single DB | Sin moving parts | OLAP roba CPU del OLTP → mover a read replica |

## Roadmap Argus específico

1. Crear tablas/vistas `stg_scans`, `cln_scans`, `agg_scan_metrics` en el mismo DB (no idéal, ver fase 3).
2. Mover lectura de dashboards de tablas raw a `agg_*`.
3. Migrar capas RAW/STG a **read replica** o a DW externo (DuckDB/BigQuery) para aislar carga.
4. dbt project con tests; `dbt run` triggered por GitHub Actions tras merge a main.
5. Lineage doc auto-generado.

## Referencias

- `docs/db/cdc-design.md`
- `docs/db/dw-export-design.md`
- `scripts/db/dw-export.sql`
- `scripts/db/materialized-views.sql`
