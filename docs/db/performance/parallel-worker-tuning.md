# Parallel worker tuning (Pack 48-H Round 5 · #141)

## Parámetros relacionados

```text
max_worker_processes        -- cap global workers
max_parallel_workers        -- cap workers paralelos totales
max_parallel_workers_per_gather
max_parallel_maintenance_workers  -- para CREATE INDEX parallel opcional
parallel_leader_participation
```

## Estrategia

1. Baseline: `EXPLAIN` sin paralelismo vs con paralelismo en queries batch.
2. Subir `max_parallel_workers_per_gather` gradualmente (2→4) observando CPU saturation.
3. Separar roles: `reporting` alto, `app` bajo.

## Mantenimiento

- `VACUUM` puede usar parallelism (`max_parallel_maintenance_workers`).
- `CREATE INDEX` puede usar `PARALLEL` workers (PG11+).

## Argus

- No maximizar paralelismo en tier pequeño Render: puede empeorar latencia p95 API compartiendo CPU.

## Referencias

- `docs/db/postgres-topics/parallel-queries.md`
