# Migration CI checks (Pack 48-H Round 6 · #164)

## Pipeline mínimo

1. Spin Postgres efímero (testcontainers / docker compose).
2. `alembic upgrade head` (debe pasar).
3. `alembic downgrade -1 && alembic upgrade head` (idempotencia).
4. Schema drift vs golden (`schema-drift-check.py`).
5. Squawk lint sobre SQL migrations.
6. pgTAP tests (`scripts/db/test/*`).
7. Data quality smoke (`data-quality.sql` subset rápido).
8. Performance regression (EXPLAIN snapshot top queries).

## Gates

- Falla cualquier paso → bloquea merge.
- Warnings (drift menor) → comment PR.

## Argus

Workflow file vivirá en infra repo, no en `docs/db/`. Esto es spec.

## Referencias

- `docs/db/migration-tooling-deep.md`
- `docs/db/testing/strategies.md`
