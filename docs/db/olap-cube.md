# OLAP cube design (Pack 48-H Round 4 · #122)

## OLTP vs OLAP

- **OLTP** (PG hoy): muchos `INSERT`/`UPDATE`, queries point-lookup por PK, dashboards en tiempo real.
- **OLAP**: pocas escrituras (batch), queries que escanean millones de filas, group by amplios, dimensiones cruzadas.

Para Argus, los reportes (`#121`) ya empiezan a estresar el OLTP. Cuando crezca el volumen, conviene separar OLAP en su propia capa con un **star schema**.

## Star schema propuesto

```
              ┌─────────────────────┐
              │  dim_dates          │
              │  date_key (PK)      │
              │  day, week, month   │
              └──────────┬──────────┘
                         │
   ┌─────────────────────┴─────────────────────┐
   │              fact_scans                    │
   │  scan_id (PK), date_key, company_id,        │
   │  player_uuid, plugin_id, verdict_key,        │
   │  duration_sec, risk_score, violations_count │
   └─────┬───────┬───────┬───────┬───────┬──────┘
         │       │       │       │       │
         ▼       ▼       ▼       ▼       ▼
   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐ ┌──────────────┐
   │ dim_   │ │ dim_   │ │ dim_   │ │ dim_       │ │ dim_         │
   │ comp.  │ │ player │ │ plugin │ │ verdict    │ │ ai_model     │
   └────────┘ └────────┘ └────────┘ └────────────┘ └──────────────┘
```

## Fact tables

### `fact_scans`

| Columna | Tipo | Notas |
| --- | --- | --- |
| scan_id | BIGINT | grain = un scan |
| date_key | INT | FK → dim_dates |
| time_key | SMALLINT | hora del día (0-23) |
| company_id | INT | FK → dim_companies |
| player_uuid_hash | TEXT | pseudonimizado |
| plugin_id | INT | FK → dim_plugins |
| verdict_key | SMALLINT | FK → dim_verdicts |
| ai_model_key | INT | FK → dim_ai_models |
| duration_sec | NUMERIC | medida |
| risk_score | NUMERIC | medida |
| violations_count | INT | medida |
| is_banned | BOOLEAN | medida (count helper) |

### `fact_decisions` (one row per Oracle decision)

Idem con `confidence_score`, `verdict`, `model_version_key`.

### `fact_violations` (one row per violation)

Detalle de cheats detectados.

## Dim tables (slowly changing dimensions)

| Dim | SCD type | Notas |
| --- | --- | --- |
| `dim_companies` | SCD 2 | guarda historia de plan changes |
| `dim_players` | SCD 1 (overwrite) | nombre puede cambiar |
| `dim_plugins` | SCD 2 | versión del plugin |
| `dim_verdicts` | SCD 0 (static) | enum: clean/suspicious/ban/error |
| `dim_ai_models` | SCD 2 | model_version, hyperparams |
| `dim_dates` | static | poblada por script |

## Pre-aggregations

Tablas resumen on top:

| Tabla | Granularidad |
| --- | --- |
| `agg_scans_day_company` | día × company |
| `agg_scans_hour_company` | hora × company (24h) |
| `agg_decisions_week_model` | semana × modelo |
| `agg_violations_day_type` | día × violation_type |

Estas se refrescan con `INSERT ... ON CONFLICT` desde fact tables.

## Tools

| Opción | Pros | Contras |
| --- | --- | --- |
| **dbt + PG** | familiar, gratis | OLAP en mismo PG → competencia de IO |
| **dbt + DuckDB** | sin server, archivos Parquet, query rapidísimo | manual sync, no realtime |
| **dbt + ClickHouse** | OLAP nativo, compresión 10×, SQL casi compat | infra extra |
| **dbt + BigQuery** | escala infinita, SQL standard | costo por TB scanned, lock-in |
| **Apache Druid** | sub-segundo, time-series | infra Java compleja |
| **Cube.dev** | semantic layer + caching | requiere backend node |

## Recomendación Argus

**Etapa actual (Pack 48-52)**: pre-aggregations en PG (MVs ya entregadas en #90). Cubre reportes diarios y dashboards.

**Etapa media (Pack 52-60)**: dbt + DuckDB **local** o en S3 con Parquet:
- Export incremental nocturno (ver `dw-export-design.md`).
- DuckDB lee Parquet directo, sin servidor.
- Reportes con duración >5s migran a DuckDB.

**Etapa avanzada (Pack 60+)**: si crecen >10TB de fact_scans, mover a ClickHouse. Mantener PG como OLTP puro.

## Anonimización en el camino

Toda fila que llegue al DW pasa por:

1. Drop columnas PII-H: `last_ip`, `password_hash`, `session_token`.
2. Hash columnas PII-M: `argus_hash_pii(player_uuid, 'dw')`, `argus_hash_pii(email, 'dw')`.
3. Truncate IPs: `argus_anonymize_ip(ip)`.
4. Aggregate counts en lugar de detail rows cuando posible.

(Ver `data-classification.md` (#102) y `dw-export.sql` Round 2.)

## Queries demo en el cube

```sql
-- Top 10 violadores cross-empresa (anonimizado)
SELECT player_uuid_hash, SUM(violations_count) AS total
FROM fact_scans
WHERE date_key BETWEEN 20260401 AND 20260430
GROUP BY 1
ORDER BY total DESC LIMIT 10;

-- Ban rate por modelo
SELECT m.version,
       100.0 * SUM(CASE WHEN f.is_banned THEN 1 ELSE 0 END) / COUNT(*) AS ban_rate
FROM fact_scans f
JOIN dim_ai_models m ON m.id = f.ai_model_key
GROUP BY m.version;

-- Día más activo del mes pasado
SELECT d.day, SUM(violations_count) AS v
FROM fact_violations f
JOIN dim_dates d ON d.date_key = f.date_key
WHERE d.year_month = '2026-04'
GROUP BY d.day ORDER BY v DESC LIMIT 5;
```

## Roadmap entrega

| Pack | Entregable |
| --- | --- |
| 50 | Generar `dim_dates` (script Python: 5 años) |
| 51 | ETL incremental fact_scans → PG schema `olap_*` |
| 52 | dbt project + tests |
| 53 | DuckDB query layer + analyst dashboard |
| 56+ | Migration a ClickHouse si volume justifica |

## Costos estimados (DuckDB era)

- $0 software.
- Storage S3 Parquet: 0.5GB/mes/cliente comprimido → barato.
- Compute: en CI/laptops analyst.

vs. BigQuery:

- $20/TB scanned → ~$100/mes para 10 analysts haciendo queries.
- $0.02/GB/mes storage.
- Free tier first 10GB y 1TB queries.

## Referencias

- `dw-export-design.md` (Round 2) — export anonimizado.
- `etl-pipeline-design.md` (#93) — stages.
- `materialized-views.md` (#90) — MVs como pre-aggregations.
- `data-classification.md` (#102).
