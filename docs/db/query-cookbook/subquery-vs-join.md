# Subquery vs JOIN (Pack 48-H Round 6 · #156)

## Equivalencias comunes

```sql
-- Subquery
SELECT * FROM scans WHERE company_id IN (SELECT id FROM companies WHERE tier='pro');

-- JOIN
SELECT s.* FROM scans s JOIN companies c ON c.id = s.company_id WHERE c.tier='pro';
```

PG suele planificar ambas igual; diferencias surgen con `NOT IN` + NULLs, `EXISTS` semantics.

## Reglas

- `EXISTS` prefiere sobre `IN` cuando subset grande.
- `NOT IN` con NULL puede devolver vacío → preferir `NOT EXISTS`.

## LEFT JOIN ... IS NULL pattern

Encontrar huérfanos:

```sql
SELECT s.id FROM scans s LEFT JOIN companies c ON c.id = s.company_id WHERE c.id IS NULL;
```

## Argus

Tests integridad usan este patrón (`integrity-checks.sql`).

## Referencias

- `docs/db/query-cookbook/cte-vs-subquery.md`
