# N+1 elimination (Pack 48-H Round 6 · #156)

## Anti-patrón

```python
for c in companies:
    scans = db.execute("SELECT * FROM scans WHERE company_id = %s", c.id)
```

## Patrones de fix

### 1. Batch IN

```sql
SELECT * FROM scans WHERE company_id = ANY($1::int[]);
```

### 2. JOIN explícito

```sql
SELECT c.id, c.name, s.*
FROM companies c JOIN scans s ON s.company_id = c.id
WHERE c.id = ANY($1::int[]);
```

### 3. Window con `row_number()`

Top N por grupo sin loop app.

### 4. LATERAL JOIN

Top N por compañía (`postgres-topics/lateral-joins.md`).

### 5. Dataloader (GraphQL)

`graphql-layer.md` (Round 4).

## Detección

- APM con span DB count por request.
- `pg_stat_statements` ratio `calls / requests`.

## Argus

Auditar endpoints panel y reportes; ver `query-performance.md` (Round 2).

## Referencias

- `docs/db/query-cookbook/lateral-join-recipes.md`
