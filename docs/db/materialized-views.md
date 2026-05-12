# Argus Projects — Materialized views (Pack 48-H Round 3 · #90)

## Por qué

Las queries del panel (`/dashboard`, `/companies/<id>/overview`, `/oracle/stats`) hoy se calculan **on-demand** sobre `scans`, `ai_decisions_log`, `plugin_violations`. A volúmenes de 100k+ filas/día, esto:

- Hace que el dashboard tarde 1-5s (visto en `query-performance.md`).
- Consume CPU constante en el primario (sin replicas, ver `read-replicas-design.md`).
- Genera lecturas masivas que ensucian shared_buffers.

Las **MV (materialized views)** precalculan agregaciones y se sirven en O(1).

## Vistas propuestas

### 1. `mv_daily_scan_stats`

Por `(company_id, día)`:
- total scans, completed, banned, error, avg duration.
- ban_rate (% scans con verdict='ban').
- avg violations per scan.
- top verdict.

**Refresh:** `CONCURRENTLY` cada **5 min** (via `pg_cron` o cron externo).
**Tamaño esperado:** ~12k filas/año por company (≤1MB).

### 2. `mv_player_profiles_summary`

Por `(company_id, player_uuid)`:
- total_scans, total_violations, banned_count.
- last_scan_at, last_violation_type.
- "risk_tier" derivado (avg_risk_score buckets).

**Refresh:** cada **15 min**.
**Tamaño:** ~1 fila por jugador por company (depende del juego, estimado <500k).

### 3. `mv_oracle_confidence_distribution`

Histograma por `(company_id, bucket_5pct)`:
- count, avg_score, %verdict='ban' en ese bucket.
- Permite curva ROC manual para calibrar Oracle.

**Refresh:** cada **30 min**.
**Tamaño:** ~20 filas por company.

### 4. `mv_plugin_health_metrics`

Por `(company_id, server_name)`:
- last_seen, scans_last_hour, scans_last_day, error_rate.
- "status" derivado (healthy/stale/down).

**Refresh:** cada **1 min** (este es near-real-time).
**Tamaño:** ~10 filas por company.

## Estrategia de refresh

| MV | Frecuencia | Mecanismo | Lag aceptable |
| --- | --- | --- | --- |
| `mv_daily_scan_stats` | 5 min | pg_cron / cron externo | 5 min |
| `mv_player_profiles_summary` | 15 min | pg_cron | 15 min |
| `mv_oracle_confidence_distribution` | 30 min | pg_cron | 30 min |
| `mv_plugin_health_metrics` | 1 min | pg_cron | 1 min |

**Requisito clave:** `REFRESH MATERIALIZED VIEW CONCURRENTLY` requiere un índice UNIQUE en la MV. Lo cumplimos definiendo `UNIQUE INDEX` por la combinación natural (`company_id, día`, etc.).

## Trade-offs

| Tema | Riesgo | Mitigación |
| --- | --- | --- |
| Stale data | Dashboard muestra datos 5min viejos | Etiquetar UI con "refreshed: HH:MM"; para casos críticos, query directa. |
| Refresh cost | Recalcular MV grande puede bloquear | Usar `CONCURRENTLY`; particionar la base table primero. |
| Storage extra | Cada MV duplica espacio agregado | Aceptable: total <100MB para las 4 MVs proyectadas. |
| Concurrent refresh races | dos cron jobs concurrentes | Lock advisory: `SELECT pg_try_advisory_lock(hashtext('mv_daily_scan_stats'))`. |

## Application code changes (alto nivel)

`web_app/app.py` hoy hace:

```sql
SELECT DATE(started_at), COUNT(*) FROM scans
WHERE company_id = ? AND started_at >= NOW() - INTERVAL '30 days'
GROUP BY 1 ORDER BY 1;
```

Pasa a:

```sql
SELECT day, total_scans FROM mv_daily_scan_stats
WHERE company_id = ? AND day >= CURRENT_DATE - 30 ORDER BY day;
```

**No** cambiar app code en este Round (scope D). Sólo dejar las MVs listas para que un futuro commit las consuma.

## Observabilidad

```sql
SELECT matviewname, ispopulated, definition
FROM pg_matviews WHERE schemaname='public';

-- tamaño
SELECT relname, pg_size_pretty(pg_total_relation_size(c.oid))
FROM pg_class c JOIN pg_matviews m ON m.matviewname=c.relname;

-- último refresh (no hay catálogo nativo; usar tabla custom):
SELECT * FROM mv_refresh_log ORDER BY refreshed_at DESC LIMIT 20;
```

Las helpers (`mv_refresh_log`, función `refresh_mv()`) están en `scripts/db/materialized-views.sql`.

## Plan de adopción

1. Crear MVs y `mv_refresh_log` en staging.
2. Validar tamaño y tiempo de refresh con clone de prod.
3. Habilitar refresh cron (no consumir aún desde app).
4. Crear feature flag `dashboard_use_mv=true`; un endpoint sirve MV, otro la query original; comparar respuestas.
5. Switch 100% tras 1 semana sin diff.
