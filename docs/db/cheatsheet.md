# PG/Argus DB cheatsheet (Pack 48-H Round 4 · #131)

Atajos operativos para usar en consola/Slack. **Ninguno destructivo sin warning**.

## Conectarse

```bash
psql "$DATABASE_URL?sslmode=require"
psql -h <host> -U <user> -d <db>            # contraseña en PGPASSWORD
\conninfo                                    # ver conexión actual
```

## Navegación schema

```sql
\dt                       -- list tables (current schema)
\dt+ public.*             -- tables con size
\d+ scans                 -- describe table (cols, idx, FK)
\di public.*              -- list indexes
\dv                       -- views
\dm                       -- materialized views
\df argus_*               -- functions
\dT                       -- types
\du                       -- users/roles
\l+                       -- databases con size
\dn                       -- schemas
\dp scans                 -- permisos
\dx                       -- extensiones instaladas
```

Programáticamente:

```sql
SELECT relname, pg_size_pretty(pg_total_relation_size(oid)) AS total
FROM pg_class WHERE relkind='r' ORDER BY pg_total_relation_size(oid) DESC LIMIT 20;
```

## Sesiones / conexiones

```sql
SELECT pid, usename, application_name, client_addr, state, query_start, query
FROM pg_stat_activity
WHERE state <> 'idle'
ORDER BY query_start;
```

```sql
SELECT count(*) FILTER (WHERE state='active') AS active,
       count(*) FILTER (WHERE state='idle') AS idle,
       count(*) FILTER (WHERE state='idle in transaction') AS idle_in_tx,
       count(*) AS total
FROM pg_stat_activity;
```

Kill conexión (cuidado):

```sql
SELECT pg_cancel_backend(<pid>);             -- soft, intenta cancelar query
SELECT pg_terminate_backend(<pid>);          -- hard, mata conexión
```

## Locks

```sql
SELECT pid, locktype, relation::regclass, mode, granted,
       pg_blocking_pids(pid) AS blocked_by
FROM pg_locks WHERE NOT granted;
```

Bloqueadores top:

```sql
SELECT bl.pid AS blocked, bl.usename AS user, bl.query AS query_b,
       kl.pid AS blocker, kl.usename AS by, kl.query AS query_k
FROM pg_stat_activity bl
JOIN pg_locks lk_bl ON lk_bl.pid = bl.pid AND NOT lk_bl.granted
JOIN pg_locks lk_k ON lk_k.locktype=lk_bl.locktype AND lk_k.granted
JOIN pg_stat_activity kl ON kl.pid = lk_k.pid AND kl.pid <> bl.pid;
```

## Slow queries

```sql
SELECT round(total_exec_time::numeric,1) AS total_ms,
       calls, round(mean_exec_time::numeric,1) AS mean_ms,
       round((100*total_exec_time/sum(total_exec_time) OVER ())::numeric,1) AS pct,
       left(query, 120) AS q
FROM pg_stat_statements
ORDER BY total_exec_time DESC LIMIT 20;
```

Reset stats:

```sql
SELECT pg_stat_statements_reset();
```

## EXPLAIN

```sql
EXPLAIN (ANALYZE, BUFFERS, SETTINGS, FORMAT TEXT) SELECT ...;
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT ...;   -- stable
```

Indicadores rojos:

- `Seq Scan on big_table`
- `Rows Removed by Filter: N` con N alto
- `Sort` con `Memory:` que dice "Disk:"
- `Nested Loop` con outer scan retornando >1000 rows.

## Vacuum / analyze

```sql
VACUUM (VERBOSE, ANALYZE) public.scans;
VACUUM (FULL) public.scans;                   -- bloqueante; ventana
REINDEX TABLE CONCURRENTLY scans;
ANALYZE scans;
```

Estado:

```sql
SELECT relname, n_live_tup, n_dead_tup,
       round(100.0*n_dead_tup/NULLIF(n_live_tup,0), 1) AS dead_pct,
       last_vacuum, last_autovacuum, last_analyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC LIMIT 20;
```

## Tamaño

```sql
SELECT pg_size_pretty(pg_database_size(current_database()));
SELECT pg_size_pretty(pg_total_relation_size('public.scans'));
SELECT relname, pg_size_pretty(pg_relation_size(oid)) AS heap,
       pg_size_pretty(pg_indexes_size(oid)) AS indexes,
       pg_size_pretty(pg_total_relation_size(oid)) AS total
FROM pg_class WHERE relkind='r' ORDER BY pg_total_relation_size(oid) DESC LIMIT 10;
```

## Índices

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_scans_company_created
ON scans(company_id, created_at DESC);

DROP INDEX CONCURRENTLY IF EXISTS idx_old;
REINDEX INDEX CONCURRENTLY idx_x;
```

Índices no usados:

```sql
SELECT s.schemaname, s.relname, s.indexrelname,
       pg_size_pretty(pg_relation_size(s.indexrelid)) AS size, s.idx_scan
FROM pg_stat_user_indexes s
WHERE s.idx_scan = 0 AND s.indexrelid NOT IN (
    SELECT indexrelid FROM pg_index WHERE indisunique OR indisprimary
)
ORDER BY pg_relation_size(s.indexrelid) DESC LIMIT 20;
```

## Backup / restore

```bash
pg_dump --format=custom --no-owner --no-privileges \
  -h <host> -U <user> -d <db> -f argus.dump

pg_restore -d <newdb> --no-owner --no-privileges argus.dump
```

Solo schema:

```bash
pg_dump --schema-only -d argus > argus-schema.sql
```

Solo data de una tabla:

```bash
pg_dump --data-only --table=public.scans -d argus -f scans.sql
```

## Roles / permisos

```sql
CREATE ROLE app_ro NOLOGIN;
GRANT CONNECT ON DATABASE argus TO app_ro;
GRANT USAGE ON SCHEMA public TO app_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_ro;
```

Revocar all default:

```sql
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
```

## Replication

```sql
SELECT * FROM pg_stat_replication;             -- primary view
SELECT * FROM pg_stat_wal_receiver;            -- replica view
SELECT pg_is_in_recovery();                    -- ¿soy replica?
SELECT pg_last_wal_replay_lsn(), pg_current_wal_lsn();
```

## WAL / disk

```sql
SELECT pg_size_pretty(pg_current_wal_lsn() - '0/0'::pg_lsn);
```

## Timezone / fechas

```sql
SHOW timezone;
SET TIME ZONE 'UTC';
SELECT now(), now() AT TIME ZONE 'UTC', now() AT TIME ZONE 'America/Argentina/Buenos_Aires';
```

## Operaciones útiles para Argus

### Top 10 companies por scans (24h)

```sql
SELECT company_id, count(*) FROM scans
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
```

### Distribución de risk_score

```sql
SELECT width_bucket(risk_score, 0, 100, 10) AS bucket, count(*)
FROM scans WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY 1 ORDER BY 1;
```

### Latest ban per player

```sql
SELECT DISTINCT ON (player_uuid) player_uuid, banned_at, reason
FROM ban_history ORDER BY player_uuid, banned_at DESC;
```

### Find duplicate player_uuid per company (data quality)

```sql
SELECT company_id, player_uuid, count(*)
FROM ai_player_profiles
GROUP BY 1, 2 HAVING count(*) > 1;
```

## Quoting / escape

```sql
SELECT $$tab	with\n$$;                          -- dollar-quoted
INSERT INTO t (v) VALUES (E'\\path\\to');           -- E-string
SELECT format('Hi %I, your id is %L', name, id);    -- safe identifier+literal
```

## psql shortcuts útiles

```text
\timing on
\x auto                  -- expanded display on tables wide
\pset null '∅'
\watch 2                 -- repeat last query every 2s
\copy table TO 'file.csv' CSV HEADER
\copy table FROM 'file.csv' CSV HEADER
\set AUTOCOMMIT off
ROLLBACK; COMMIT;
```

## Variables de entorno comunes

| Var | Uso |
| --- | --- |
| `PGHOST` | host |
| `PGPORT` | port |
| `PGUSER` | usuario |
| `PGPASSWORD` | password |
| `PGDATABASE` | DB |
| `PGAPPNAME` | aparece en `pg_stat_activity` |
| `PGSSLMODE` | `require`, `verify-ca`, `verify-full` |

## Referencias internas

- `dba-runbook.md`
- `edge-cases-playbook.md` (#95)
- `monitoring-queries.sql`
- `cheatsheet.md` (este file)
- `anti-patterns.md` (#132)
