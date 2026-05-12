# Recursive CTEs (Pack 48-H Round 5 · #140)

## Patrón grafo / jerarquía

```sql
WITH RECURSIVE tree AS (
  SELECT id, parent_id, 1 AS depth FROM org_units WHERE parent_id IS NULL
  UNION ALL
  SELECT c.id, c.parent_id, t.depth + 1
  FROM org_units c
  JOIN tree t ON c.parent_id = t.id
  WHERE t.depth < 20
)
SELECT * FROM tree;
```

## Límites

- Siempre `WHERE depth < N` para evitar ciclos infinitos.
- Ciclos requieren detección (`ARRAY` path o `cycle` PG14+).

## Argus

- Cadena de `referral` o jerarquías staff (si existen).
- Menos común que window functions para series temporales.

## Referencias

- `docs/db/postgres-topics/lateral-joins.md`
