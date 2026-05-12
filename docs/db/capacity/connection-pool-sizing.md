# Connection pool sizing (Pack 48-H Round 6 · #161)

## Reglas de pulgar

- Total PG connections necesarias ≈ `workers_app * pool_per_worker + replicas * connect`.
- Mantener `< 0.7 * max_connections` para evitar errores en bursts.
- Cada conexión idle consume ~5-10 MB RAM PG.

## Con PgBouncer (transaction pooling)

- Pool server-side: 10-30 conexiones a PG aunque clients sean cientos.
- `default_pool_size` por DB.
- Atención a features incompatibles (prepared statements server-side, `LISTEN/NOTIFY`).

## Argus

Configuración propuesta en `scripts/db/pgbouncer.ini` (Round 3) + `docs/db/connection-pool.md`.

## Referencias

- `docs/db/render-runbook.md`
