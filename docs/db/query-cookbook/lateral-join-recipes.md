# LATERAL JOIN recipes (Pack 48-H Round 6 · #156)

## Recipe 1 · Top 3 scans por compañía

```sql
SELECT c.id, s.*
FROM companies c
CROSS JOIN LATERAL (
  SELECT id, risk_score, created_at FROM scans
  WHERE company_id = c.id
  ORDER BY created_at DESC LIMIT 3
) s;
```

## Recipe 2 · Métrica calculada por fila

```sql
SELECT s.id, s.risk_score, m.bucket
FROM scans s
CROSS JOIN LATERAL (
  SELECT CASE WHEN s.risk_score < 25 THEN 'low' WHEN s.risk_score < 75 THEN 'mid' ELSE 'high' END
  AS bucket
) m;
```

## Recipe 3 · Join con función set-returning

```sql
SELECT s.id, x.elem
FROM scans s
CROSS JOIN LATERAL jsonb_array_elements_text(s.tags) AS x(elem);
```

## Performance

`CROSS JOIN LATERAL` con `LIMIT` interno típicamente más eficiente que window functions cuando N pequeño.

## Referencias

- `docs/db/postgres-topics/lateral-joins.md`
