# Window functions catalog (Pack 48-H Round 4 · #118)

Window functions = aggregates **sin colapsar filas**. Mantienen el grano de la query pero permiten "mirar alrededor" (partición / orden / frame).

## Sintaxis general

```sql
fn(args) OVER (
    [PARTITION BY col, ...]
    [ORDER BY col [ASC|DESC], ...]
    [ROWS|RANGE|GROUPS frame_clause]
)
```

## Funciones más útiles

| Función | Qué hace |
| --- | --- |
| `ROW_NUMBER()` | número de fila único en la partición |
| `RANK()` | rank con huecos en empates (1,1,3) |
| `DENSE_RANK()` | rank sin huecos (1,1,2) |
| `NTILE(n)` | divide la partición en n buckets |
| `LAG(col, k)` | valor de k filas atrás |
| `LEAD(col, k)` | valor de k filas adelante |
| `FIRST_VALUE(col)` | primer valor en la ventana |
| `LAST_VALUE(col)` | último (cuidado con frame default) |
| `NTH_VALUE(col, k)` | k-ésimo valor |
| `SUM/AVG/COUNT/MIN/MAX(col) OVER` | aggregate como window |
| `CUME_DIST()` | distribución acumulada |
| `PERCENT_RANK()` | rank percentil |

## Frames (default vs explicit)

```sql
... OVER (ORDER BY x)
    -- equivale a:
    -- RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW

... OVER (ORDER BY x ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
    -- toda la partición
```

**Gotcha**: `LAST_VALUE` con default frame devuelve la fila actual (porque el frame termina en CURRENT ROW). Siempre escribir frame explícito al usar `LAST_VALUE`.

---

## 20 queries útiles para Argus

### 1. Top 5 jugadores por scans en cada empresa

```sql
SELECT company_id, player_uuid, scan_count
FROM (
  SELECT company_id, player_uuid, COUNT(*) AS scan_count,
         ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY COUNT(*) DESC) AS rn
  FROM scans
  GROUP BY company_id, player_uuid
) t
WHERE rn <= 5;
```

### 2. Ban rate corrido sobre últimas 7 ventanas diarias por empresa

```sql
SELECT company_id, day,
       SUM(banned) OVER (
         PARTITION BY company_id
         ORDER BY day
         ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
       ) AS banned_last_7d
FROM mv_daily_scan_stats;
```

### 3. Tiempo desde el scan anterior por jugador

```sql
SELECT id, player_uuid, started_at,
       started_at - LAG(started_at) OVER (PARTITION BY player_uuid ORDER BY started_at)
         AS gap_since_prev
FROM scans;
```

### 4. Detección rápida de "spam" (jugador con >5 scans en 1 min)

```sql
SELECT *
FROM (
  SELECT id, player_uuid, started_at,
         started_at - LAG(started_at, 4) OVER (PARTITION BY player_uuid ORDER BY started_at)
           AS span_last_5
  FROM scans
) t
WHERE span_last_5 < INTERVAL '1 minute';
```

### 5. Promedio móvil 30d de risk_score

```sql
SELECT id, player_uuid, started_at, risk_score,
       AVG(risk_score) OVER (
         PARTITION BY player_uuid
         ORDER BY started_at
         RANGE BETWEEN INTERVAL '30 days' PRECEDING AND CURRENT ROW
       ) AS risk_avg_30d
FROM scans;
```

### 6. Percentil del risk_score en su empresa

```sql
SELECT id, company_id, risk_score,
       PERCENT_RANK() OVER (PARTITION BY company_id ORDER BY risk_score) AS pct
FROM scans;
```

### 7. Compañías ranked por scans hoy

```sql
SELECT company_id, scans_today,
       DENSE_RANK() OVER (ORDER BY scans_today DESC) AS rank
FROM (
  SELECT company_id, COUNT(*) AS scans_today
  FROM scans WHERE started_at >= CURRENT_DATE
  GROUP BY 1
) t;
```

### 8. Diferencia con el día anterior

```sql
SELECT company_id, day, total_scans,
       total_scans - LAG(total_scans) OVER (PARTITION BY company_id ORDER BY day) AS delta_day
FROM mv_daily_scan_stats;
```

### 9. Acumulado mensual

```sql
SELECT company_id, day, total_scans,
       SUM(total_scans) OVER (
         PARTITION BY company_id, date_trunc('month', day)
         ORDER BY day
       ) AS cumulative_month
FROM mv_daily_scan_stats;
```

### 10. Primer/último verdict del jugador

```sql
SELECT player_uuid, started_at, verdict,
       FIRST_VALUE(verdict) OVER (PARTITION BY player_uuid ORDER BY started_at) AS first_v,
       LAST_VALUE(verdict)  OVER (PARTITION BY player_uuid
                                  ORDER BY started_at
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS last_v
FROM scans;
```

### 11. Tasa de cambio (% día sobre día)

```sql
SELECT day, total_scans,
       100.0 * (total_scans - LAG(total_scans) OVER (ORDER BY day))
       / NULLIF(LAG(total_scans) OVER (ORDER BY day), 0) AS pct_change
FROM mv_daily_scan_stats;
```

### 12. Buckets de risk_score por NTILE

```sql
SELECT id, risk_score, NTILE(10) OVER (ORDER BY risk_score) AS decile
FROM scans;
```

### 13. Próximo evento por jugador

```sql
SELECT id, player_uuid, started_at,
       LEAD(started_at) OVER (PARTITION BY player_uuid ORDER BY started_at) AS next_event
FROM scans;
```

### 14. Ratio del jugador vs su empresa

```sql
SELECT id, company_id, player_uuid, risk_score,
       risk_score / NULLIF(AVG(risk_score) OVER (PARTITION BY company_id), 0) AS ratio_vs_company_avg
FROM scans;
```

### 15. Rolling COUNT distinct (jugadores únicos últimos 7d) por empresa

```sql
-- PG no soporta DISTINCT en window directamente; aproximación con CTE
WITH per_day AS (
  SELECT company_id, day, COUNT(DISTINCT player_uuid) AS uniq
  FROM (
    SELECT company_id, date_trunc('day', started_at) AS day, player_uuid
    FROM scans WHERE started_at >= NOW() - INTERVAL '60 days'
  ) z GROUP BY 1, 2
)
SELECT *,
       SUM(uniq) OVER (PARTITION BY company_id ORDER BY day
                       ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS uniq_sum_7d
FROM per_day;
```

### 16. Detectar gaps (sin actividad)

```sql
SELECT player_uuid, started_at,
       started_at - LAG(started_at) OVER (PARTITION BY player_uuid ORDER BY started_at) AS gap
FROM scans
WHERE started_at - LAG(started_at) OVER (...) > INTERVAL '30 days';
```

### 17. Top-N por empresa + cliente

```sql
SELECT *
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY company_id ORDER BY risk_score DESC) AS r
  FROM scans
  WHERE started_at >= NOW() - INTERVAL '1 day'
) t
WHERE r <= 10;
```

### 18. Mediana móvil

```sql
SELECT day,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_scans)
         OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS median_7d
FROM mv_daily_scan_stats;
```

(En PG ≥10.)

### 19. Diferencia con mismo día semana pasada

```sql
SELECT day, total_scans,
       total_scans - LAG(total_scans, 7) OVER (ORDER BY day) AS yoy_wow
FROM mv_daily_scan_stats;
```

### 20. Hot streaks: rachas de scans con verdict='ban'

```sql
SELECT player_uuid, started_at, verdict,
       SUM(CASE WHEN verdict='ban' THEN 1 ELSE 0 END)
         OVER (PARTITION BY player_uuid ORDER BY started_at) AS streak
FROM scans;
```

(Aproximación; para "racha **consecutiva**" exacta usar gaps-and-islands.)

## Gaps-and-islands

Patrón clásico: encontrar rachas consecutivas. PG idiom:

```sql
-- detectar bloques contiguos de scans 'ban' por jugador
SELECT player_uuid, MIN(started_at) AS streak_start, MAX(started_at) AS streak_end, COUNT(*) AS len
FROM (
  SELECT *,
         ROW_NUMBER() OVER (PARTITION BY player_uuid ORDER BY started_at) -
         ROW_NUMBER() OVER (PARTITION BY player_uuid, verdict ORDER BY started_at) AS grp
  FROM scans
) t
WHERE verdict='ban'
GROUP BY player_uuid, grp;
```

## Perf tips

1. Window functions corren **después** de WHERE/JOIN/GROUP BY. No las uses para filtrar; envolvé en subquery.
2. ORDER BY de la window puede aprovechar índice si coincide con el ORDER BY de la query.
3. Para top-N por partición, `ROW_NUMBER() + filter` es casi siempre más rápido que `LIMIT` correlated.
4. Frame `ROWS` es más rápido que `RANGE` cuando la columna no es contigua.

## Anti-patterns

1. ❌ `WHERE row_number() OVER (...) = 1` (sintaxis inválida).
2. ❌ `LAST_VALUE` sin frame explícito.
3. ❌ Window con `ORDER BY` aleatorio (no determinístico).
4. ❌ Calcular agregaciones GROUP BY y luego "deshacerlas" con join cuando window haría el trabajo.

## Referencias

- PG docs §3.5 "Window Functions".
- `query-performance.md` (Round 2) — usar ventanas en lugar de subqueries correlacionadas.
