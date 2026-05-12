# Argus current state (Pack 48-H Round 6 · #160)

## Hoy

- **Dev**: SQLite local (rápido, sin deps).
- **Prod**: PostgreSQL en Render.
- Schema embedded en `web_app/app.py` (`_plugin_schema_guard`, `init_*`).
- Sin Alembic; migrations implícitas vía `CREATE IF NOT EXISTS` / `ALTER TABLE` en boot.

## Brechas vs target Pack 49+

- Alembic ownership pendiente.
- F-001 (`scans.company_id`) pendiente.
- Multi-tenant aislamiento por convención (no RLS).
- Sin offsite backups separados.

## Riesgos derivados

- Drift dev vs prod (tipos / case sensitivity).
- Boot guards no idempotentes 100%.
- Recovery confiando solo en Render.

## Plan

Ver `docs/db/pack49-migration-plan/overview.md`.

## Referencias

- `docs/db/schema-evolution.md`
- `docs/db/findings-pack48.md`
