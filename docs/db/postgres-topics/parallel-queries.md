# Parallel query execution (Pack 48-H Round 5 · #140)

## Concepto

PostgreSQL puede lanzar **workers** paralelos para scans/agregaciones grandes (`Gather`, `Parallel Seq Scan`).

## Parámetros clave

```text
max_parallel_workers_per_gather
max_parallel_workers
max_worker_processes
parallel_setup_cost
parallel_tuple_cost
min_parallel_table_scan_size
min_parallel_index_scan_size
```

## Cuándo ayuda

- Tablas grandes sin índice selectivo (aunque mejor arreglar índice primero).
- Agregaciones masivas en reporting batch.

## Cuándo perjudica

- OLTP pequeño con muchas queries cortas → overhead coordinación.
- `SET max_parallel_workers_per_gather = 0` para queries sensibles (via role).

## Argus

- Jobs batch analytics nocturnos: permitir paralelismo moderado.
- API interactiva: limitar por rol (`ALTER ROLE app SET max_parallel_workers_per_gather = 2`).

## EXPLAIN

Buscar `Parallel` nodes y `Workers Planned`.

## Referencias

- `docs/db/performance/parallel-worker-tuning.md`
