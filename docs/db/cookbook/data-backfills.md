# Data backfills (Pack 48-H Round 6 · #165)

## Reglas

- En **batches** (5k-50k filas) con `LIMIT` + condición avance.
- `COMMIT` por batch (procedure) o transacciones separadas (script externo).
- Idempotente: incluir `WHERE new_col IS NULL` o similar.
- Loggear progreso (`backfill_runs(id, table, rows_done, finished_at)`).

## Plantilla

```sql
UPDATE scans
   SET company_id = u.company_id
  FROM users u
 WHERE scans.user_id = u.id
   AND scans.company_id IS NULL
   AND scans.ctid IN (
     SELECT ctid FROM scans WHERE company_id IS NULL LIMIT 5000
   );
```

Repetir hasta `0 rows affected`.

## Argus

F-001 backfill exacto vive en `pack49-migration-plan/F-001-fix.md`.

## Referencias

- `docs/db/cookbook/idempotent-migrations.md`
