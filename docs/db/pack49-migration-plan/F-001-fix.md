# F-001 fix plan (`scans.company_id`) (Pack 48-H Round 5 · #149)

## Hallazgo

`scans` carece de `company_id` formal esperado por aislamiento multi-tenant (ver `findings-pack48.md`).

## Plan técnico (DDL + datos)

### Fase A · Add column nullable

```sql
ALTER TABLE scans ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scans_company_created ON scans(company_id, created_at DESC);
```

### Fase B · Backfill

Estrategia depende de datos existentes:

| Fuente verdad provisional | Query backfill (ejemplo) |
| --- | --- |
| `users.company_id` via `scans.user_id` | `UPDATE scans s SET company_id = u.company_id FROM users u WHERE s.user_id = u.id AND s.company_id IS NULL` |
| Plugin/server mapping | **REVIEW** con modelo real |

Ejecutar en **batches** (`WHERE ctid IN (SELECT ctid FROM scans WHERE company_id IS NULL LIMIT 5000)`).

### Fase C · NOT NULL

Tras 100% backfill + app escribiendo siempre `company_id`:

```sql
ALTER TABLE scans ALTER COLUMN company_id SET NOT NULL;
```

Usar patrón `NOT VALID` constraints si aplica (ver `migration-tooling-deep.md`).

### Fase D · RLS

Ver `rls-enablement.md`.

## Validación

- `scripts/db/tenant-isolation-checks.sql` re-habilitar checks removidos por F-001.
- pgTAP nuevos tests.

## Riesgos

- Locks en tabla grande → índices `CONCURRENTLY`, batches off-peak.

## Owner

DBA + dev app (D) coordinando despliegue.
