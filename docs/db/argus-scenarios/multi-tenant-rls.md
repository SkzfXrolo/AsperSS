# Multi-tenant RLS for Argus (Pack 48-H Round 5 · #147)

## Motivación

Mitigar F-012: aislamiento sólo por convención `WHERE company_id` en app es frágil.

## Fases

1. **F-001 fix**: asegurar `scans.company_id` poblada y NOT NULL.
2. Habilitar RLS en tablas tenant-scoped: `scans`, `violations`, `ai_decisions_log`, `ai_player_profiles`, etc.
3. Establecer `SET app.current_company_id` en middleware tras auth.
4. Tests `tenant-isolation-checks.sql` + nuevos tests pgTAP.

## Tablas globales

`users` multi-tenant vía membership — policy más compleja (JOIN).

## Rollout

- Shadow mode: policy `USING (true)` logging (no recomendado prod) → mejor staging full RLS primero.

## Referencias

- `docs/db/pack49-migration-plan/rls-enablement.md`
- `docs/db/security-advanced/row-level-security.md`
