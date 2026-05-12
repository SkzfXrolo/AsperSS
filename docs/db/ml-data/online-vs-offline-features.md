# Online vs offline features (Pack 48-H Round 5 · #137)

## Definiciones

| Tipo | Latencia | Consistencia | Ejemplos Argus |
| --- | --- | --- | --- |
| **Online** | ms–s | Debe estar en request path | score agregado últimas N scans en panel |
| **Offline** | min–días | Batch OK | features para entrenamiento, reportes mensuales |

## Online: patrones

- Precompute en **MV** refresh corto (`materialized-views.md`).
- Cache Redis con TTL + key por `player_uuid`.
- Consulta SQL acotada con índices (`additional-indexes.sql`).

## Offline: patrones

- dbt job nocturno.
- Export a Parquet particionado por `dt=YYYY-MM-DD`.

## Training-serving skew

Riesgo: feature offline calculada distinto que online.

Mitigación:

- Compartir **misma definición SQL** (macro dbt importada en app como vista).
- Tests de paridad (`testing/strategies.md`).

## Referencias

- `docs/db/ml-data/feature-storage.md`
- `docs/db/ml-data/time-series-storage.md`
