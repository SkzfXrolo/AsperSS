# Row-Level Security deep (Pack 48-H Round 5 · #146)

## Modelo Argus

Forzar `company_id = current_setting('app.current_company_id')::int` en policies.

```sql
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON scans
  USING (company_id = current_setting('app.current_company_id', true)::int);
```

## Bypass

- Superuser / `BYPASSRLS` attribute → evitar en roles app.
- `SET ROLE` auditing.

## Performance

- Cada policy añade predicates → asegurar índices alineados.
- `SELECT`-only workloads: considerar vista security-barrier (avanzado).

## Bootstrap sesión

Al conectar (pooler statement):

```sql
SET app.current_company_id = '123';
```

## Referencias

- `docs/db/argus-scenarios/multi-tenant-rls.md`
- `docs/db/security-hardening.md`
