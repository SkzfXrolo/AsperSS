# Window functions recipes (Pack 48-H Round 6 · #156)

## Recipe 1 · Ranking por grupo

```sql
SELECT *, ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY created_at DESC) AS rn
FROM scans;
```

## Recipe 2 · Running sum diario

```sql
SELECT day, count(*) AS n,
       SUM(count(*)) OVER (ORDER BY day) AS running_total
FROM (
  SELECT date_trunc('day', created_at) AS day FROM scans
) t GROUP BY day;
```

## Recipe 3 · Diff vs previous (LAG)

```sql
SELECT id, risk_score,
       LAG(risk_score) OVER (PARTITION BY player_uuid ORDER BY created_at) AS prev,
       risk_score - LAG(risk_score) OVER (PARTITION BY player_uuid ORDER BY created_at) AS delta
FROM scans;
```

## Recipe 4 · Top-N por grupo con tiebreaker

```sql
SELECT *
FROM (
  SELECT *, RANK() OVER (PARTITION BY company_id ORDER BY risk_score DESC, created_at DESC) AS rk
  FROM scans
) t WHERE rk <= 5;
```

## Argus

Ver `window-functions.md` (Round 4) para catálogo completo.

## Referencias

- `docs/db/window-functions.md`
