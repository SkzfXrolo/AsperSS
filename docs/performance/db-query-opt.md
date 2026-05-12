# Database Query Optimization Runbook (Pack48-G)

## 1) Identificar slow queries

- Activar `pg_stat_statements`.
- Ranking por `total_time` y `mean_time`.

## 2) Leer EXPLAIN ANALYZE

- Buscar:
  - Seq Scan en tablas grandes.
  - Hash join spilling.
  - Sort cost alto.
  - Rows estimadas vs reales muy distintas.

## 3) Decidir estrategia

- Reescritura SQL
- Nuevo índice
- Cache

## 4) Patrones comunes

- N+1
- Missing index
- Full table scan
- JOIN con cardinalidad explosiva

## 5) Herramientas

- pganalyze
- pgMustard
- query advisor interno
