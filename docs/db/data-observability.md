# Data observability (Pack 48-H Round 4 · #129)

## ¿Qué es?

> Data observability = la capacidad de **detectar, diagnosticar y resolver** problemas de calidad/disponibilidad de datos antes que afecten downstream (analytics, ML, billing).

Cinco pilares (Monte Carlo Data, Gartner):

1. **Freshness** — ¿cuándo se actualizó por última vez una tabla?
2. **Volume** — ¿cantidad de rows está dentro de bandas históricas?
3. **Schema** — ¿cambió la forma (cols, tipos)?
4. **Distribution** — ¿valores en rangos esperados?
5. **Lineage** — ¿de dónde viene y a dónde va cada dato?

## ¿Por qué importa para Argus?

Argus alimenta downstream:

- Dashboards staff (panel scans/ban rate).
- Modelos Oracle (player risk score, training data).
- Reportes facturación (usage por company).
- Auditoría compliance (DSAR, GDPR).

Una tabla que deja de poblarse 4h pasa **silencioso** sin observability → falsos negativos, decisiones equivocadas.

## Detección por pilar

### 1. Freshness

Métrica clave: `now() - max(created_at)` por tabla.

```sql
SELECT 'scans' AS tbl, max(created_at) AS latest, EXTRACT(EPOCH FROM NOW()-max(created_at))/60 AS minutes_stale FROM scans
UNION ALL SELECT 'ai_decisions_log', max(timestamp), EXTRACT(EPOCH FROM NOW()-max(timestamp))/60 FROM ai_decisions_log
UNION ALL SELECT 'staff_audit_log', max(created_at), EXTRACT(EPOCH FROM NOW()-max(created_at))/60 FROM staff_audit_log;
```

SLA propuesta por tabla:

| Tabla | SLA freshness | Acción si excede |
| --- | --- | --- |
| `scans` | <5 min | page DBA on-call |
| `ai_decisions_log` | <10 min | warn |
| `staff_audit_log` | <60 min | warn |
| `companies` | <24h | info |
| `cache_*` | <1h | info |

### 2. Volume

Métrica clave: filas insertadas en ventana N (e.g. 1h).

```sql
SELECT date_trunc('hour', created_at) AS h, count(*) AS n
FROM scans
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY 1 ORDER BY 1;
```

Anomalía: usar **3-sigma** sobre baseline (media histórica ± 3·stddev) o **MAD** (median absolute deviation, más robusto).

Receta sencilla:

```sql
WITH per_hour AS (
  SELECT date_trunc('hour', created_at) AS h, count(*) AS n
  FROM scans
  WHERE created_at >= NOW() - INTERVAL '30 days'
  GROUP BY 1
),
stats AS (
  SELECT avg(n) AS mu, stddev_pop(n) AS sigma
  FROM per_hour
  WHERE h < date_trunc('hour', NOW())
)
SELECT h, n, mu, sigma, (n-mu)/NULLIF(sigma,0) AS z_score
FROM per_hour CROSS JOIN stats
WHERE h >= NOW() - INTERVAL '2 hours' AND ABS((n-mu)/NULLIF(sigma,0)) > 3;
```

### 3. Schema

Comparar contra `golden-schema.sql` (#R3 #103). Script `schema-drift-check.py` (#100) corre weekly.

Eventos de schema change:

```sql
SELECT n.nspname, c.relname, c.relkind, c.relhasoids,
       to_timestamp(c.reloptions) AS approx,
       pg_size_pretty(pg_relation_size(c.oid)) AS sz
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r','p')
ORDER BY c.relname;
```

PostgreSQL event triggers detectan DDL en tiempo real:

```sql
CREATE FUNCTION argus_log_ddl() RETURNS event_trigger AS $$
BEGIN
  INSERT INTO ddl_log(event, command_tag, schema_name, object_name, executed_at, by_user)
  VALUES (TG_EVENT, TG_TAG, current_schema, current_query(), now(), current_user);
END$$ LANGUAGE plpgsql;

CREATE EVENT TRIGGER argus_ddl_audit ON ddl_command_end
EXECUTE FUNCTION argus_log_ddl();
```

(REVIEW: requiere superuser; Render maybe no permite.)

### 4. Distribution

Para columnas críticas: monitorear histograma vs baseline.

| Columna | Métrica | Alerta |
| --- | --- | --- |
| `scans.risk_score` | distribución por bucket (0-25, 25-50, 50-75, 75-100) | shift >20% en bucket alto |
| `ai_decisions_log.verdict` | % BAN vs WARN vs ALLOW | shift >10% absoluto |
| `users.country` | top-10 cardinality | nuevo país top-10 |
| `scans.created_at` | dist horaria | gap >2h en horario business |
| `companies.tier` | rows por tier | shift inesperado |

Sample query:

```sql
SELECT
  CASE
    WHEN risk_score < 25 THEN 'low'
    WHEN risk_score < 50 THEN 'mid'
    WHEN risk_score < 75 THEN 'high'
    ELSE 'critical'
  END AS bucket,
  date_trunc('hour', created_at) AS h,
  count(*) AS n
FROM scans
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY 1, 2 ORDER BY 2, 1;
```

### 5. Lineage

Lineage = grafo de dependencias dato → dato.

| Origen | Destino |
| --- | --- |
| `scans` | `ai_decisions_log`, `mv_daily_scan_stats`, DW `fact_scans` |
| `ai_decisions_log` | `mv_oracle_confidence_distribution`, reports `incident-report.sql` |
| `users` | `staff_audit_log`, DW `dim_users` |
| `companies` | reports, billing system |

Documentar en `lineage.md` (futuro Pack). Tool candidate: `dbt docs` o `openlineage`.

## Plataforma de observability

| Capa | Tool | Costo | Madurez |
| --- | --- | --- | --- |
| Métricas DB | Prometheus + `postgres_exporter` | gratis | alta |
| Logs DB | Render dashboard / Datadog | $ | alta |
| Data quality | Great Expectations (Python) | gratis | media |
| Lineage | OpenLineage + Marquez | gratis | media |
| Anomaly | dbt + elementary | gratis | media |
| Suite | Monte Carlo, Soda, Bigeye | $$$ | alta (enterprise) |

Recomendación Argus Pack 49-52:

1. Métricas via `postgres_exporter` (ya planeado en `dashboards-spec.md`).
2. Data quality: empezar con `data-quality.sql` (Round 2) corrido vía cron, output a `data_quality_runs` tabla.
3. Lineage: documentación markdown manual hasta Pack 55, evaluar dbt cuando OLAP cube (#122) esté en marcha.

## Schema de `data_quality_runs`

```sql
CREATE TABLE IF NOT EXISTS data_quality_runs (
    id            BIGSERIAL PRIMARY KEY,
    run_id        UUID DEFAULT gen_random_uuid(),
    check_name    TEXT NOT NULL,
    target_table  TEXT,
    status        TEXT CHECK (status IN ('pass','warn','fail','error')),
    rows_checked  BIGINT,
    rows_failed   BIGINT,
    metric_value  NUMERIC,
    threshold     NUMERIC,
    details       JSONB,
    started_at    TIMESTAMPTZ DEFAULT NOW(),
    duration_ms   BIGINT
);
CREATE INDEX IF NOT EXISTS idx_dqr_started ON data_quality_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_dqr_status_started ON data_quality_runs(status, started_at DESC);
```

Wrapper Python (referenciar más adelante): ejecuta cada check de `data-quality.sql` y persiste resultado.

## Alerting

| Severidad | Canal | Ejemplos |
| --- | --- | --- |
| P0 | page + Slack #ops | freshness `scans` >30min, volume drop >80% |
| P1 | Slack #data-ops | schema drift, distribution shift >50% |
| P2 | email diario | volumen ligeramente bajo, distribution shift 10-50% |
| P3 | weekly digest | stats normales, top-N updates |

## Calidad de datos = parte del CI

Cada PR que toca DB debe correr:

1. Schema drift check (`schema-drift-check.py`).
2. Migrations forward + downgrade (`testing-strategies.md`).
3. Sample queries de `data-quality.sql` contra DB efímera con seed.

## Métricas a publicar (Prometheus)

- `argus_table_freshness_seconds{table=...}`
- `argus_table_rowcount_hourly{table=...}`
- `argus_data_quality_pass{check=...}`
- `argus_schema_drift_total`
- `argus_distribution_shift_percent{column=...}`

## Playbook · "Tabla X está stale"

1. Confirmar: `SELECT max(created_at) FROM x;`
2. Revisar app logs: ¿hay errors al insertar?
3. Revisar DB locks: `SELECT * FROM pg_locks ...`
4. Revisar disk full / autovacuum starvation.
5. Revisar cambios recientes en código (`git log -- web_app/`).
6. Si app rota: rollback release.

## Playbook · "Distribución shift inesperado"

1. Confirmar con muestra manual.
2. Revisar si hay deploy reciente que cambió lógica.
3. Buscar si hay tenant nuevo (skew por adopción).
4. Aislar por company_id para localizar foco.
5. Si es bug: tag para fix; meanwhile, anotar excepción en baseline.

## Referencias

- `data-quality.sql` (Round 2)
- `golden-schema.sql` (Round 3 · #103)
- `dashboards-spec.md` (Round 3 · #105)
- `monitoring-queries.sql` (Round 2)
- `schema-drift-check.py` (Round 3 · #100)
