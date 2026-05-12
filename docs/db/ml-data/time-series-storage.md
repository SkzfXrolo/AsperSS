# Time-series storage for ML (Pack 48-H Round 5 · #137)

## Fuentes time-series Argus

- `scans.created_at`, `risk_score`, `violations` count.
- `ai_decisions_log.timestamp`, `confidence_score`, `verdict`.
- `plugin_heartbeats` (series operativas).

## Patrones PG nativo

| Patrón | Pros | Contras |
| --- | --- | --- |
| Tabla única grande + BRIN index en tiempo | Simple | Queries complejas pueden escanear |
| Partitioning mensual (`partitioning-design.md`) | Retención por DROP partition | Ops más complejas |
| Hypertable Timescale | Continuous aggregates | Extensión extra (`timescaledb-evaluation.md`) |
| Rollup MV 5 min / 1 h | Lectura rápida panel | Staleness |

## Features rolling

Window SQL (`window-functions.md`) materializado vía MV para:

- `sum(violations)` últimos 7 días por jugador.
- `avg(confidence)` últimas 100 decisiones Oracle.

## Export ML

- Particiones `dt=` en Parquet para entrenamiento.
- Evitar leakage: cortar series al `decision_time` del label.

## Referencias

- `docs/db/partitioning-design.md`
- `docs/db/ml-data/training-data-versioning.md`
