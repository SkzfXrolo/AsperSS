# Performance Budgets (Pack48-G)

## Presupuestos backend

- Por endpoint: p50/p95/p99, payload size, query count.
- PR falla si p95 empeora >10% contra baseline.

## Presupuestos frontend por página

- LCP < 2.5s
- FID/INP < 100ms
- CLS < 0.1
- TBT y TTI dentro de objetivo del sprint

## Bundle budgets

- JS inicial por ruta: 100KB
- CSS por ruta: 50KB
- Total inicial por ruta: 200KB

## Enforcement

- Validación en CI con benchmark + reporte comparativo.
