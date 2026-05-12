# Bloat management (Pack 48-H Round 4 · #114)

## Qué es bloat

En MVCC, un `UPDATE` o `DELETE` no borra la fila: marca el tuple como muerto (`xmax`). Hasta que `VACUUM` corra, esas filas siguen ocupando páginas. **Bloat = páginas con filas muertas que ya no se ven**. Lo malo:

- Mayor IO (PG lee páginas vacías).
- Indexes referencian tuples muertos hasta `VACUUM`.
- Tabla crece en disco sin crecer en filas vivas.

Para Argus, tablas con UPDATE frecuente (`ai_player_profiles`, `plugin_servers`, `mv_*`) son los principales sospechosos. `ai_decisions_log` y `scans` son append-only → bloat bajo.

## Detección

### A) Estimación rápida (siempre disponible)

```sql
SELECT relname,
       n_live_tup,
       n_dead_tup,
       ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS pct_dead,
       pg_size_pretty(pg_total_relation_size(relid)) AS size,
       last_autovacuum, last_vacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY pct_dead DESC NULLS LAST
LIMIT 30;
```

> `pct_dead > 20%` empieza a doler. >40% es alto.

### B) Precisión exacta — `pgstattuple` (extension)

```sql
CREATE EXTENSION IF NOT EXISTS pgstattuple;

SELECT * FROM pgstattuple('scans');
-- columnas: table_len, tuple_count, tuple_len, dead_tuple_count, dead_tuple_len,
--          free_space, free_percent
```

Costo: lee la tabla entera. No correr en horas pico para tablas grandes.

Para indexes:

```sql
SELECT * FROM pgstatindex('idx_scans_company_time');
```

### C) `check_postgres.pl` (Nagios-friendly)

```bash
check_postgres.pl --action=bloat --warning=20 --critical=40
```

Útil para meter en Nagios/Zabbix.

## Herramientas para eliminar bloat

| Herramienta | Bloquea? | Espacio extra | Velocidad | Cuándo |
| --- | --- | --- | --- | --- |
| `VACUUM` | no | 0 | rápido | rutina; **no libera espacio al SO** (sólo reusa) |
| `VACUUM (FREEZE)` | no | 0 | medio | wraparound prevention |
| `VACUUM (TRUNCATE)` | no | 0 | medio | libera páginas al final si están vacías |
| `VACUUM FULL` | **AccessExclusive** | 2× tabla | lento | ventana de mantenimiento; libera 100% |
| `CLUSTER table USING idx` | **AccessExclusive** | 2× tabla | medio | re-ordena por índice + compacta |
| `pg_repack` | **no** (lock corto al final) | 2× tabla | medio | zero-downtime alternativa a VACUUM FULL |
| `pg_squeeze` | sin lock | 2× tabla | medio | similar a pg_repack, logical replication |
| Recrear tabla (CREATE + COPY + RENAME) | medio | 2× tabla | lento | full control, scriptable |

## Recomendación por caso

| Caso | Herramienta |
| --- | --- |
| Bloat <20%, append-only | autovacuum (ningún esfuerzo manual) |
| Bloat 20-40%, OLTP | `VACUUM` manual nocturno |
| Bloat >40%, tabla pequeña (<10GB) | `VACUUM FULL` en ventana |
| Bloat >40%, tabla grande | `pg_repack` |
| Re-cluster por índice (ordenar físicamente) | `CLUSTER` o `pg_repack -o idx_name` |
| Wraparound + bloat | `VACUUM FREEZE VERBOSE` |

## `pg_repack` workflow

```bash
# instalar (host): apt install postgresql-15-repack
# crear extension en DB
psql -c "CREATE EXTENSION pg_repack;"

# ejecutar zero-downtime
pg_repack -h $PGHOST -U postgres -d argus_prod -t scans \
          --no-superuser-check --jobs=4

# por índice
pg_repack -h $PGHOST -U postgres -d argus_prod -t scans -o idx_scans_company_time
```

Cómo funciona: crea tabla shadow, copia con triggers, swap. Necesita PK o UNIQUE.

## Bloat de índices

Los índices también acumulan páginas muertas. Detección:

```sql
SELECT * FROM pgstatindex('idx_scans_company_time');
-- avg_leaf_density < 70% → re-create
```

Solución:

- `REINDEX INDEX CONCURRENTLY idx_scans_company_time;` (PG12+)
- Lock muy corto, dura más que un index normal pero no bloquea writes.

## Plan de mantenimiento Argus

### Mensual

- Ejecutar `scripts/db/bloat-check.sql` en read replica.
- Reportar top 10 tablas y top 10 índices con bloat.
- Si hay alguno >40%: ticket + planificar.

### Trimestral

- `pg_repack` sobre las 3-5 tablas con mayor bloat.
- `REINDEX CONCURRENTLY` sobre top índices.

### En cada incident relacionado a IO

- Verificar bloat antes de upgradar tier.

## Settings de prevención

```sql
-- ya cubierto en autovacuum-tuning.md
ALTER TABLE ai_player_profiles SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.05
);
```

## Riesgos

| Riesgo | Mitigación |
| --- | --- |
| `VACUUM FULL` bloquea | sólo en ventana, app en mantenimiento |
| `pg_repack` requiere PK | toda tabla Argus la tiene (verificar) |
| `pg_repack` falla si DDL concurrente | freeze migrations durante repack |
| `REINDEX` aumenta IO temporal | correr en off-peak |
| Render no permite pg_repack en tier bajo | escalar tier u optar por VACUUM FULL en window |

## Anti-patterns

1. ❌ `VACUUM FULL` durante horas pico.
2. ❌ Ignorar bloat hasta que la DB ocupa 2× lo esperado.
3. ❌ Desactivar autovacuum "porque va lento" → wraparound + bloat.
4. ❌ Reusar PK de tabla vieja al recrear (sequence quedó atrás).

## Referencias

- `wraparound-prevention.md` (#113)
- `autovacuum-tuning.md` (#115)
- `edge-cases-playbook.md` (#95) — bloat como síntoma de un incidente
- `scripts/db/bloat-check.sql` (#114) — query lista
