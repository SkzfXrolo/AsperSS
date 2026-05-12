# Multi-tenant schema options (Pack 48-H Round 6 · #162)

| Opción | Aislamiento | Costo ops | Escala tenants |
| --- | --- | --- | --- |
| Shared DB / shared schema (current Argus) | bajo (col `company_id` + RLS) | mínimo | alto |
| Shared DB / schema-per-tenant | medio | medio | medio |
| DB-per-tenant | alto | alto | bajo |
| Hybrid: VIP DBs + shared rest | medio-alto | medio-alto | mixto |

Detalle ya en `multi-tenant-patterns.md` (Round 4). Este doc enfatiza:

- **Argus stays shared/shared + RLS** Pack 48-55.
- Plantearse "schema per tenant" sólo si **muy pocos enterprise** exigen aislamiento físico extremo.

## Referencias

- `docs/db/multi-tenant-patterns.md`
- `docs/db/argus-scenarios/multi-tenant-rls.md`
