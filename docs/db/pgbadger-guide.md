# PgBadger guide (Pack 48-H Round 4 · #110)

## Qué es

PgBadger es un analizador de logs de PostgreSQL. Parsea los archivos `postgresql-YYYYMMDD.log`, calcula estadísticas y emite un reporte HTML con gráficos: top queries por tiempo, distribución temporal, lock waits, errores, conexiones, etc.

Funciona "post-mortem": no consume DB en vivo, sólo lee logs. Cero impacto en producción.

## Setup mínimo

### 1. Configurar Postgres para emitir logs útiles

En `postgresql.conf`:

```
logging_collector = on
log_destination = 'stderr'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 200      # ms: queries más cortas se descartan
log_line_prefix = '%t [%p] %u@%d/%a '
log_statement = 'ddl'
log_lock_waits = on
log_temp_files = 0
log_checkpoints = on
log_autovacuum_min_duration = 0
```

Después: `SELECT pg_reload_conf();`

### 2. Verificar que están saliendo logs

```bash
tail -f /var/log/postgresql/postgresql-$(date +%Y-%m-%d).log
```

Debería ver entradas tipo:

```
2026-05-12 13:42:07.122 UTC [12345] app@argus_prod/web duration: 543.122 ms statement: SELECT ...
```

### 3. Correr análisis

```bash
./scripts/db/pgbadger/run-analysis.sh
# o
./scripts/db/pgbadger/run-analysis.sh --incremental
```

Abre el `.html` en navegador.

## Cómo leer el reporte

### "Overview"

- Total queries, durations, lock waits, errors.
- Para Argus en estado actual esperaríamos: <50k queries/h, duración media <50ms, 0 errors.

### "Hourly statistics"

- Distribución de carga por hora.
- Identificar picos (cron, reportes pesados).

### "Top Time Consuming Queries"

- Las 20 queries que consumen más wall time **total** (calls × mean).
- Acción: si una está fuera de presupuesto, revisar índices (`additional-indexes.sql`).

### "Most Frequent Queries"

- Las 20 más ejecutadas (calls/sec).
- Si hay >100 calls/sec de la misma query: candidato a cache aplicación o MV.

### "Slowest Queries"

- p95 / max duration.
- Lo más útil para descubrir cosas como `Seq Scan` accidental.

### "Queries with high tempfile usage"

- Sorts / HashJoin que no caben en `work_mem`.
- Acción: subir `work_mem` para esa sesión o reescribir query.

### "Lock waits"

- Cuántos lock waits, sobre qué tablas.
- Si la misma tabla aparece varias veces: revisar deadlocks (`edge-cases-playbook.md`).

### "Connections"

- Total auth/min, fallos.
- Picos = problema de pool (ver `connection-pool.md`).

### "Vacuum / Autovacuum"

- Frecuencia y duración del autovacuum por tabla.
- Tabla nunca vacuumada → bloat (ver `bloat-management.md`).

## Red flags típicas

| Síntoma en pgbadger | Probable causa | Acción |
| --- | --- | --- |
| Top time consuming = una query sin WHERE indexable | falta índice | revisar `additional-indexes.sql` |
| Mismo statement repetido cada 100ms | hot loop sin caché | mover a Redis |
| Lock waits > 5s sobre `scans` | migration corriendo | mover a ventana |
| Tempfile > 100MB | sort sin índice | aumentar `work_mem` |
| Error rate > 0.1% | bugs reales | grep app logs por SQLState |

## Render specifics

Render PG no expone el FS de logs directamente. Opciones:

1. **`render logs --tail postgresql > /tmp/argus.log`** y correr pgbadger sobre eso (lossy si rota rápido).
2. **Datadog / Better Stack** integración: forward logs a S3 y correr pgbadger sobre el archivo S3.
3. **PG estable** (Render Pro/Pro+): solicitar acceso a logs via support ticket si compliance lo exige.

Recomendado para Pack 48: opción 2 (Datadog ya documentado en `dashboards-spec.md`).

## Cadencia

| Frecuencia | Tipo |
| --- | --- |
| Diaria (cron) | `--incremental`, indexa nuevo día |
| Semanal (Lunes) | Full report, share con tech team |
| Post-incidente | Ad-hoc con `--since`/`--until` acotando la ventana |

## Alertas (futuras)

Pipeline: pgbadger JSON output → parser custom → si excede umbrales → page.

```bash
./run-analysis.sh --format json --output /tmp/argus.json
python -c "
import json, sys
d = json.load(open('/tmp/argus.json'))
if d['overall_stat']['queries_duration_avg'] > 100:
    print('SLOW', file=sys.stderr); sys.exit(1)
"
```

## Limitaciones

- Sólo ve lo que logueás (queries <200ms quedan fuera).
- No tiene contexto de plan (no reemplaza `EXPLAIN ANALYZE`).
- Anonimización oculta literales, dificulta repro de queries específicas.
- En Render con logs en cloud: latency de "vi el problema → tengo el log → corro pgbadger" puede ser ~30min.

## Comparación con alternativas

| Herramienta | Tipo | Pros | Cons |
| --- | --- | --- | --- |
| pgbadger | log-based, post-mortem | gratis, complete report HTML | requires log access, no realtime |
| pg_stat_statements | catalog, live | realtime, low overhead | resets, no plans |
| pganalyze (SaaS) | hosted | bonito, alerts | $$$, vendor lock |
| auto_explain | live, per-query plan | exact plans en producción | ruido en logs |

**Pack 48 Argus**: `pg_stat_statements` + `pgbadger` semanal. Pasar a pganalyze si justifica.
