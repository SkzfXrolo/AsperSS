# GROUPING SETS, CUBE, ROLLUP (Pack 48-H Round 5 · #140)

## ROLLUP

Jerarquía de agregaciones (subtotales):

```sql
SELECT company_id, date_trunc('day', created_at) AS d, count(*)
FROM scans
GROUP BY ROLLUP (company_id, date_trunc('day', created_at));
```

## CUBE

Todas las combinaciones de dimensiones (crece exponencialmente).

## GROUPING SETS

Subconjunto explícito de combinaciones (control fino).

## Identificar filas subtotal

```sql
SELECT grouping(company_id) AS g_company, ...
```

## Argus

- Reportes billing: subtotales por `company_id` y global.
- Evitar `CUBE` grande en prod interactivo; usar MV pre-agregada.

## Referencias

- `docs/db/olap-cube.md`
