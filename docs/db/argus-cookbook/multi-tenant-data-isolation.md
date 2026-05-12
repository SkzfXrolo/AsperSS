# Multi-tenant data isolation (Pack 48-H Round 6 · #163)

## Capas

1. **Auth**: validar company_id de sesión.
2. **App**: capa repo siempre filtra `company_id`.
3. **DB**: RLS forzando aislamiento.
4. **Tests**: `tenant-isolation-checks.sql`.

## Argus

Hoy capas 1-2 parcialmente; 3-4 pendientes (Pack 49 plan).

## Referencias

- `docs/db/argus-scenarios/multi-tenant-rls.md`
