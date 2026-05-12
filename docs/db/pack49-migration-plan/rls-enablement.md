# RLS enablement plan (Pack 49) (Pack 48-H Round 5 · #149)

## Pre-reqs

- F-001 resuelto para `scans`.
- Roles `app_rw` sin `BYPASSRLS`.
- Middleware setea `SET LOCAL app.current_company_id` cada request.

## Fase 0 · Inventario tablas

Lista tablas con `company_id` NOT NULL → candidatas RLS.

## Fase 1 · Staging full

1. `ALTER TABLE ... ENABLE ROW LEVEL SECURITY`.
2. `CREATE POLICY ... USING (company_id = current_setting('app.current_company_id', true)::int)`.
3. `FORCE ROW LEVEL SECURITY` opcional para owner si mismo role.

## Fase 2 · Prod canary

- Habilitar RLS en tablas menos críticas primero (`plugin_*`).
- Monitorear errores `42501` / `insufficient_privilege`.

## Fase 3 · Tablas core

`scans`, `violations`, `ai_decisions_log`, `ai_player_profiles`.

## Rollback

- `ALTER TABLE ... DISABLE ROW LEVEL SECURITY;` (documentar ventana).

## Tests

- `docs/db/argus-scenarios/multi-tenant-rls.md` casos.
- App integration tests cross-tenant.

## Referencias

- `docs/db/security-advanced/row-level-security.md`
