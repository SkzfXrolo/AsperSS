# DB performance dashboards spec (Pack 48-H Round 3 · #105)

## Objetivo

Dos dashboards de Grafana sobre PG (datasource: PostgreSQL plugin o Prometheus + `postgres_exporter`):

1. **"Argus DB – Overview"** (SRE/DBA on-call).
2. **"Argus DB – Capacity & Cost"** (Founder / mensual).

## Stack asumido

- Grafana Cloud o self-hosted.
- Datasource A: PostgreSQL plugin con queries directas (read-only role).
- Datasource B (opcional): `postgres_exporter` → Prometheus (más eficiente para series largas).

## Convención de panel JSON

Los siguientes panels son **especificaciones lógicas**. Para importar a Grafana, encapsular en un dashboard JSON con `panels: [...]`. Ya hay JSON estructurado debajo de cada panel (puede pegarse en Grafana → New Dashboard → JSON).

---

## Dashboard 1 · "Argus DB – Overview"

### Variables

| Variable | Query | Default |
| --- | --- | --- |
| `$range` | tiempo de Grafana | last 1h |
| `$datname` | `SELECT datname FROM pg_database WHERE NOT datistemplate` | argus_prod |

### Panel 1.1 — Connections (stat)

```sql
SELECT
  COUNT(*) FILTER (WHERE state='active')               AS active,
  COUNT(*) FILTER (WHERE state='idle')                 AS idle,
  COUNT(*) FILTER (WHERE state='idle in transaction')  AS idle_tx,
  COUNT(*)                                             AS total
FROM pg_stat_activity
WHERE datname = '$datname';
```

```json
{
  "type": "stat",
  "title": "Connections",
  "targets": [{"refId": "A", "rawSql": "SELECT COUNT(*) FILTER (WHERE state='active') AS active, COUNT(*) FILTER (WHERE state='idle') AS idle, COUNT(*) FILTER (WHERE state='idle in transaction') AS idle_tx, COUNT(*) AS total FROM pg_stat_activity WHERE datname = '$datname'"}],
  "fieldConfig": {"defaults": {"thresholds": {"steps": [{"color": "green", "value": 0}, {"color": "yellow", "value": 60}, {"color": "red", "value": 90}]}}}
}
```

### Panel 1.2 — Query rate (timeseries)

Necesita `pg_stat_statements`:

```sql
SELECT
  $__timeGroup(NOW(), '1m') AS time,
  SUM(calls) AS calls
FROM pg_stat_statements
GROUP BY 1 ORDER BY 1;
```

Alternativa sin pg_stat_statements: derivar de `pg_stat_database.xact_commit + xact_rollback` con `irate`.

### Panel 1.3 — Slow queries / min (>1s)

```sql
SELECT $__time(query_start),
       COUNT(*) AS slow
FROM pg_stat_activity
WHERE state = 'active' AND NOW() - query_start > INTERVAL '1 second'
GROUP BY 1;
```

### Panel 1.4 — Cache hit ratio (stat)

```sql
SELECT
  ROUND(100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit + heap_blks_read), 0), 2)
       AS cache_hit_pct
FROM pg_statio_user_tables;
```

> Objetivo: >99%. <95% → investigar shared_buffers / dataset > RAM.

### Panel 1.5 — WAL generation rate (bytes/s)

```sql
SELECT
  $__timeGroup(NOW(), '1m') AS time,
  pg_wal_lsn_diff(pg_current_wal_lsn(), LAG(pg_current_wal_lsn()) OVER ())
  / EXTRACT(EPOCH FROM (NOW() - LAG(NOW()) OVER ()))
       AS wal_bytes_per_sec;
```

(Mejor con `postgres_exporter` que mantiene serie persistente.)

### Panel 1.6 — Lock waits (current)

```sql
SELECT pid, NOW() - query_start AS waiting_for, query, wait_event
FROM pg_stat_activity
WHERE wait_event_type='Lock'
ORDER BY waiting_for DESC LIMIT 20;
```

(Tipo: tabla.)

### Panel 1.7 — Replication lag

```sql
SELECT
  application_name,
  pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS bytes_behind,
  replay_lag
FROM pg_stat_replication;
```

### Panel 1.8 — Disk usage by table (top 20)

```sql
SELECT
  schemaname || '.' || relname AS table,
  pg_size_pretty(pg_total_relation_size(relid)) AS size,
  pg_total_relation_size(relid) AS size_bytes
FROM pg_catalog.pg_statio_user_tables
ORDER BY size_bytes DESC
LIMIT 20;
```

### Panel 1.9 — Dead tuples (top 20)

```sql
SELECT relname,
       n_live_tup,
       n_dead_tup,
       ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS pct_dead
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY pct_dead DESC NULLS LAST
LIMIT 20;
```

### Panel 1.10 — Unused indexes

```sql
SELECT schemaname || '.' || relname AS table,
       indexrelname AS index,
       idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;
```

---

## Dashboard 2 · "Argus DB – Capacity & Cost"

### Panel 2.1 — DB size over time

```sql
SELECT $__time(NOW()), pg_database_size('argus_prod') AS bytes;
```

(Capturar diariamente y graficar con Prometheus o histórico custom.)

### Panel 2.2 — Top tables growth rate

(Requiere snapshots semanales en una tabla `db_size_snapshot`. Calcular delta.)

### Panel 2.3 — Connections cap utilization

```sql
SELECT
  COUNT(*)                                                         AS used,
  current_setting('max_connections')::int                          AS max,
  ROUND(100.0 * COUNT(*) / current_setting('max_connections')::int, 2) AS pct
FROM pg_stat_activity;
```

Threshold: >80% → considerar PgBouncer (`docs/db/connection-pool.md`).

### Panel 2.4 — Backup status

(Custom: registrar último backup en `mv_refresh_log` o tabla similar.)

### Panel 2.5 — Bloat top 10

```sql
SELECT relname,
       pg_size_pretty(pg_total_relation_size(relid)) AS total,
       pg_size_pretty(pg_total_relation_size(relid) -
                      pg_relation_size(relid)) AS bloat_approx
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) - pg_relation_size(relid) DESC
LIMIT 10;
```

(Aproximación; para precisión usar `pgstattuple`.)

### Panel 2.6 — Estimated monthly cost

(Variable manual: tier de Render + size + replicas. Ver `cost-forecast.md`.)

---

## Alertas asociadas

| Panel | Alerta | Threshold |
| --- | --- | --- |
| 1.1 Connections | total > 90% max | warning/critical |
| 1.4 Cache hit | <95% sostenido 30min | warning |
| 1.5 WAL rate | >2× baseline 15min | warning |
| 1.7 Replication lag | bytes_behind > 100MB o lag > 60s | critical |
| 1.8 Disk by table | growth ×2 semana sobre semana | warning |
| 2.3 Connections cap | >80% | warning |
| 2.4 Backup status | último >25h atrás | critical |

Integrar con PagerDuty / Slack según `on-call-playbook.md`.

## Importación

1. Crear datasource PostgreSQL **read-only** (role `monitor_ro` con `SELECT` a `pg_stat_*`).
2. Crear empty dashboard.
3. Por panel: paste JSON + adjust target ids.
4. Probar variable `$datname`.
5. Save dashboard → exportar JSON → versionar en repo (futuro: `infra/grafana/dashboards/`).
