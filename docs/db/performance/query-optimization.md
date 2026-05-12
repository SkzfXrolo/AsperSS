# Query optimization patterns (Pack 48-H Round 5 · #141)

## Flujo de trabajo

1. Medir con `EXPLAIN (ANALYZE, BUFFERS)` en staging con datos representativos.
2. Identificar nodos caros (Seq Scan, Sort, Nested Loop grande).
3. Aplicar patrón (índice, rewrite, MV, estadísticas).
4. Re-medir; guardar plan baseline en repo tests perf.

## Patrones frecuentes

| Síntoma | Fix típico |
| --- | --- |
| Seq scan grande | índice adecuado o BRIN temporal |
| Sort spill | `work_mem` bump puntual `SET LOCAL` |
| Bad nested loop | `SET enable_nestloop=off` sólo debug; fix estadísticas |
| Estimación filas mal | `ANALYZE`, aumentar `default_statistics_target` selectivo |
| OR expansión | rewrite `UNION ALL` |

## Argus

- Panel queries: asegurar `company_id` + `created_at` en predicates con índice compuesto.

## Referencias

- `docs/db/query-performance.md`
- `scripts/db/explain-templates.sql`
