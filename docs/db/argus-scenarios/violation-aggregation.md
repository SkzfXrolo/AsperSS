# Violation aggregation (Pack 48-H Round 5 · #147)

## Objetivo

Reducir costo de queries "últimos N días violaciones por jugador" mediante pre-agregación.

## Opciones

| Opción | Descripción |
| --- | --- |
| MV incremental | refresh cada 5 min |
| Tabla rollup | job ETL nightly |
| Continuous aggregate | Timescale (si adoptado) |

## Esquema rollup ejemplo

`violations_daily(player_uuid, company_id, day, cnt, max_severity)`

## Referencias

- `scripts/db/reports/monthly-summary.sql`
- `docs/db/materialized-views.md`
