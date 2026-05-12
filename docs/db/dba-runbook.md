# Argus Projects — DBA runbook (operaciones) — Pack 48-H Round 2

## Índice rápido

1. [Agregar índice sin bloqueo](#agregar-índice-sin-bloqueo)
2. [VACUUM / ANALYZE / REINDEX](#vacuum--analyze--reindex)
3. [Bloat (tablas e índices)](#bloat)
4. [Matar query trabajada](#matar-query-trabajada)
5. [On-call: alta CPU en Postgres](#on-call-alta-cpu-en-postgres)

---

## Agregar índice sin bloqueo

```sql
-- NUNCA en transacción grande de deploy síncrono:
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_name ON table_name (col1, col2 DESC);

-- Verificar validez:
SELECT indexrelname, indisvalid FROM pg_index i
JOIN pg_class c ON c.oid = i.indexrelid
WHERE c.relname = 'idx_name';
```

**Si falla:** `DROP INDEX CONCURRENTLY idx_name;` y reintentar tras resolver lock.

---

## VACUUM / ANALYZE / REINDEX

| Comando | Uso | Lock |
| --- | --- | --- |
| `VACUUM ANALYZE scans;` | Rutina post-mass-delete | `ShareUpdateExclusive` corto |
| `VACUUM (VERBOSE, ANALYZE) plugin_violations;` | Dead tuples altos | similar |
| `REINDEX INDEX CONCURRENTLY idx_foo;` | Índice corrupto / bloat severo | bajo vs `REINDEX TABLE` |

Evitar `VACUUM FULL` salvo ventana larga (bloquea escritura).

---

## Bloat

1. Consultar `monitoring-queries.sql` M5 (dead_pct).
2. Si `dead_pct` > 40% en `scans`: `VACUUM ANALYZE` + revisar long transactions.
3. Extensión `pg_repack` para reescribir tabla online (instalación admin).

---

## Matar query trabajada

```sql
-- 1) Identificar pid (ver monitoring M7)
SELECT pid, query FROM pg_stat_activity WHERE state <> 'idle';

-- 2) Cancelar (SIGINT) — preferible
SELECT pg_cancel_backend(12345);

-- 3) Terminar (SIGKILL) — sólo si cancel no responde en 30s
SELECT pg_terminate_backend(12345);
```

Registrar en ticket: query text, usuario, duración.

---

## On-call: alta CPU en Postgres

| Paso | Acción |
| --- | --- |
| 1 | Grafana / Render metrics: ¿CPU DB 100% y app normal? |
| 2 | `pg_stat_activity`: query larga accidental (`SELECT *` sin LIMIT) |
| 3 | `pg_stat_statements` (si extensión habilitada): top mean_time |
| 4 | Mitigación inmediata: `pg_cancel_backend` del offender |
| 5 | Mitigación estructural: índice faltante (`EXPLAIN ANALYZE` desde `explain-templates.sql`) |
| 6 | Post-mortem: PR con índice o rewrite |

### Alertas Grafana (placeholder)

- Panel: `pg_stat_database_numbackends`
- Alert: `avg(rate(...)) > max_connections * 0.85`

---

## Contacto escalamiento

1. Owner producto
2. Si indisponibilidad > 15 min: considerar failover Render (support ticket)
