# Autovacuum tuning (Pack 48-H Round 4 · #115)

## ¿Qué hace autovacuum?

1. Marca filas muertas como reusables (`VACUUM`).
2. Actualiza estadísticas para el planner (`ANALYZE`).
3. Previene wraparound (`VACUUM FREEZE` cuando hace falta).

PG corre **autovacuum workers** que escanean tablas según umbrales basados en updates/deletes.

## Defaults PG y cuándo cambiarlos

| Parámetro | Default | Qué hace | Cuándo subir/bajar |
| --- | --- | --- | --- |
| `autovacuum` | on | enable feature | dejar on **siempre** |
| `autovacuum_max_workers` | 3 | workers concurrentes | subir a 4-6 si hay muchas tablas grandes |
| `autovacuum_naptime` | 1 min | tiempo entre checks | bajar a 15s si tablas muy activas |
| `autovacuum_vacuum_threshold` | 50 | mínimo tuples muertos | bajar a 25 en tablas pequeñas |
| `autovacuum_vacuum_scale_factor` | 0.2 | % de tabla para gatillar | **bajar** a 0.05 en tablas grandes |
| `autovacuum_analyze_threshold` | 50 | tuples cambiados antes de ANALYZE | tablas chicas: 25 |
| `autovacuum_analyze_scale_factor` | 0.1 | % | bajar a 0.02 en tablas grandes |
| `autovacuum_vacuum_cost_delay` | 2ms | pausa entre páginas | subir si IO saturado |
| `autovacuum_vacuum_cost_limit` | 200 | "presupuesto" antes de pausa | subir a 1000 en máquinas con SSD |
| `autovacuum_freeze_max_age` | 200M | XIDs antes de freeze obligatorio | bajar a 100M en tablas críticas |

## Reglas heurísticas

### Tabla pequeña activa (<100k filas)

```sql
ALTER TABLE plugin_servers SET (
    autovacuum_vacuum_threshold = 25,
    autovacuum_analyze_threshold = 25
);
```

### Tabla mediana (100k–1M)

Defaults globales OK.

### Tabla grande (>1M, append-heavy: `scans`, `ai_decisions_log`)

```sql
ALTER TABLE scans SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_freeze_max_age = 100000000,
    fillfactor = 95           -- append-only: poco overhead UPDATE
);
```

### Tabla con muchos UPDATEs (`ai_player_profiles`, `mv_*`)

```sql
ALTER TABLE ai_player_profiles SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.05,
    fillfactor = 90           -- HOT updates baratos
);
```

## Cuánto puede vacuumear sin saturar IO

`autovacuum_vacuum_cost_limit` (default 200) marca el presupuesto antes de pausar `cost_delay` ms. Para SSD modernos:

```sql
ALTER SYSTEM SET autovacuum_vacuum_cost_limit = 1000;
ALTER SYSTEM SET autovacuum_vacuum_cost_delay = 2;
SELECT pg_reload_conf();
```

(Render: depende del tier; verificar `current_setting('autovacuum_vacuum_cost_limit')`.)

## Detección de starvation

```sql
-- tablas que deberían haber sido vacuumeadas y no
SELECT relname, n_dead_tup, n_live_tup,
       last_autovacuum,
       age(NOW(), last_autovacuum) AS since,
       last_analyze
FROM pg_stat_user_tables
WHERE n_dead_tup > GREATEST(50, n_live_tup * 0.2)
ORDER BY n_dead_tup DESC LIMIT 20;
```

Si una tabla nunca aparece con `last_autovacuum` reciente:

1. ¿`autovacuum_enabled = false` por error en `ALTER TABLE`?
2. ¿Workers ocupados con otras tablas?
3. ¿Lock blocking autovacuum?
4. ¿XID wraparound forzando "aggressive" autovacuum sobre otra tabla?

## Aggressive autovacuum (anti-wraparound)

Cuando `relfrozenxid` de una tabla pasa `vacuum_freeze_table_age` (150M default), PG corre un autovacuum **aggressive** que congela todas las páginas. Es costoso (lee toda la tabla). Para tablas enormes, programarlo manualmente off-peak:

```sql
-- forzar congelado preventivo
VACUUM (FREEZE, VERBOSE) ai_decisions_log;
```

## Análisis del log

Habilitar:

```
log_autovacuum_min_duration = 0       -- todo
```

Genera líneas como:

```
LOG: automatic vacuum of table "argus_prod.public.scans":
     pages: 0 removed, 12345 remain, ...
     tuples: 1234 removed, 100000 remain, 50 are dead but not yet removable
     buffer usage: 12000 hits, 5000 misses, 100 dirtied
     system usage: CPU: user: 0.50 s, system: 0.20 s, elapsed: 5.20 s
```

Métricas para alertar:

| Métrica | Acción |
| --- | --- |
| `elapsed > 60 s` regularmente | tabla muy grande → particionar / pg_repack |
| `dead but not yet removable > 1000` | hay xmin viejo bloqueando → revisar tx/slots |
| `buffer usage misses >> hits` | tabla > shared_buffers; aceptable si poco frecuente |

## Manual VACUUM como complemento

```sql
-- nocturno, post-cleanup masivo
VACUUM (ANALYZE) ai_decisions_log;

-- pre-deploy, freshen stats
ANALYZE scans;
```

`VACUUM ANALYZE` después de batch DELETE/INSERT grandes evita esperar al autovacuum.

## Monitoring queries

```sql
-- autovacuum running ahora
SELECT pid, NOW() - xact_start AS age, query
FROM pg_stat_activity
WHERE query ILIKE 'autovacuum%';

-- tabla por elapsed
SELECT relname, last_autovacuum,
       autovacuum_count, vacuum_count, analyze_count
FROM pg_stat_user_tables
ORDER BY autovacuum_count DESC LIMIT 20;
```

## Settings recomendados Argus (suma)

```sql
-- en postgresql.conf / ALTER SYSTEM
ALTER SYSTEM SET autovacuum_max_workers           = 4;
ALTER SYSTEM SET autovacuum_naptime               = '30s';
ALTER SYSTEM SET autovacuum_vacuum_cost_limit     = 1000;
ALTER SYSTEM SET log_autovacuum_min_duration      = 0;
SELECT pg_reload_conf();

-- por tabla
ALTER TABLE scans                SET (autovacuum_vacuum_scale_factor=0.05, fillfactor=95);
ALTER TABLE ai_decisions_log     SET (autovacuum_vacuum_scale_factor=0.05, fillfactor=95);
ALTER TABLE plugin_violations    SET (autovacuum_vacuum_scale_factor=0.05);
ALTER TABLE staff_audit_log      SET (autovacuum_vacuum_scale_factor=0.1);
ALTER TABLE ai_player_profiles   SET (autovacuum_vacuum_scale_factor=0.05, fillfactor=90);
```

## Cuando autovacuum no alcanza

1. Aumentar `autovacuum_max_workers`.
2. Particionar tabla (#89) — cada partición se vacuumea independiente y más rápido.
3. `VACUUM` manual programado en pg_cron.
4. `pg_repack` (#114).

## Anti-patterns

1. ❌ `ALTER TABLE ... SET (autovacuum_enabled = false)` "porque molesta".
2. ❌ `autovacuum_max_workers = 10` en server con 2 vCPU.
3. ❌ Ignorar warnings de wraparound (`pg_database_size` no incluye XID age).
4. ❌ Correr `VACUUM FULL` "preventivo" semanal.

## Referencias

- `bloat-management.md` (#114) — herramientas si autovacuum no alcanza.
- `wraparound-prevention.md` (#113) — el escenario peor.
- `dba-runbook.md` — procedure manual de vacuum.
