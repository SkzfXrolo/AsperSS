# Argus Projects — Data warehouse / analytics export (Pack 48-H Round 2)

## Objetivo

Mover **carga analítica** fuera del OLTP (Render PG) hacia un DW barato (BigQuery, Snowflake, DuckDB file en S3, Motherduck) sin exponer PII cruda.

## Fuentes y frecuencia

| Tabla OLTP | Frecuencia incremental | Full | Anonimización |
| --- | --- | --- | --- |
| `scans` | hourly (`started_at > watermark`) | daily | hash(`machine_id`), truncar `minecraft_username` |
| `scan_results` | hourly por `scan_id` watermark | daily | hash paths largos |
| `ai_decisions_log` | hourly | weekly | drop `reasoning` text o summarizar |
| `plugin_violations` | hourly | weekly | pseudonymize `player_uuid` |
| `ban_history` | daily | monthly | legal review antes export |

**Watermark:** tabla `dw_sync_state(key PRIMARY KEY, last_ts TIMESTAMPTZ)` en OLTP o en DW.

## Star schema (DW)

### Fact tables

- **`fact_scans`** — grain: 1 row por `scan_id`. Measures: `risk_score`, `duration_sec`, `issues_count`, `verdict_encoded`.
- **`fact_violations`** — grain: 1 row por `violation_id`.
- **`fact_ai_decisions`** — grain: 1 row por `decision_id`.

### Dimensions

- **`dim_companies`** — `company_id`, `name`, `tier`, SCD2 opcional.
- **`dim_users`** — staff anonimizado (`user_id` → surrogate).
- **`dim_time`** — `date_id`, `hour_of_day`, `week`, `month` (generada en ETL).
- **`dim_check`** — `check_name`, `category` (Packet vs Bukkit).

### Bridges

- **`bridge_scan_results`** si se necesita granularidad file-level (puede explotar en tamaño; preferir sample 10%).

## Pipeline ETL

1. **Extract:** `COPY (SELECT …) TO STDOUT WITH CSV` desde replica read-only.
2. **Transform:** Python Polars / dbt en runner (GitHub Actions scheduled).
3. **Load:** BigQuery `LOAD JOB` o `INSERT` batch.

## PII / GDPR

- Nunca exportar `users.password_hash`, `push_subscriptions`, `registration_tokens` al DW público.
- Derecho al olvido: job que propaga `user_id = NULL` en facts históricos.

## Coste

- BigQuery: pago por TB escaneado → particionar por `event_date`.
- DuckDB + Parquet en S3: casi gratis hasta millones de rows.

Ver implementación SQL semilla en `scripts/db/dw-export.sql`.
