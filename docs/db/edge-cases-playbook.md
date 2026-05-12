# Edge cases playbook (Pack 48-H Round 3 · #95)

Operational guide for the DBA on-call. Cada sección: **síntoma → diagnóstico → mitigación → prevención**.

> ⚠️ Ninguno de estos comandos debe ejecutarse "para probar". Sólo en incidentes reales tras confirmar el diagnóstico.

---

## 1. Transaction deadlocks

**Síntoma**

```
ERROR: deadlock detected
DETAIL: Process 1234 waits for ShareLock on transaction 567; blocked by process 7890.
```

**Diagnóstico**

```sql
SELECT pid, state, wait_event_type, wait_event, query
FROM pg_stat_activity
WHERE state <> 'idle' AND wait_event_type = 'Lock';
```

`pg_locks` JOIN `pg_stat_activity`:

```sql
SELECT bl.pid AS blocked_pid, bl.query AS blocked_query,
       kl.pid AS blocking_pid, kl.query AS blocking_query
FROM pg_stat_activity bl
JOIN pg_locks         w  ON w.pid = bl.pid AND NOT w.granted
JOIN pg_locks         h  ON h.locktype = w.locktype
                        AND h.database IS NOT DISTINCT FROM w.database
                        AND h.relation IS NOT DISTINCT FROM w.relation
                        AND h.granted
JOIN pg_stat_activity kl ON kl.pid = h.pid AND kl.pid <> bl.pid;
```

**Mitigación**

- Si la víctima fue ya abortada por PG, sólo reintentar desde la app.
- Si hay deadlock recurrente: identificar pareja de tablas + orden de lock.

**Prevención**

1. Adquirir locks en **orden alfabético** de tabla en cada transacción.
2. Mantener transacciones cortas (<2s).
3. Para updates masivos: `SELECT ... FOR UPDATE SKIP LOCKED LIMIT 100` batched.
4. Activar `log_lock_waits = on`, `deadlock_timeout = 1s`.

---

## 2. Lock contention (no llega a deadlock, pero queries cuelgan)

**Síntoma**: queries en `state=active` con `wait_event_type=Lock` y `wait_event=relation` durante segundos.

**Diagnóstico**

```sql
SELECT pid, pg_blocking_pids(pid), state, age(NOW(), xact_start) AS xact_age, query
FROM pg_stat_activity
WHERE wait_event_type = 'Lock';
```

**Mitigación**

- Identificar el "head of line" (pid con la transacción más antigua que bloquea).
- Si es un cron o limpieza: `SELECT pg_cancel_backend(<pid>)` (suave) o `pg_terminate_backend(<pid>)` (duro).
- **Nunca** terminar el primer pid sin haberlo correlacionado con un usuario/proceso conocido.

**Prevención**

- Migrations: `SET lock_timeout = '5s'` antes de cada `ALTER TABLE`.
- Reportes pesados: ejecutar en read replica.

---

## 3. Long-running queries (>5min)

**Diagnóstico**

```sql
SELECT pid, now() - query_start AS dur, state, query
FROM pg_stat_activity
WHERE now() - query_start > INTERVAL '5 minutes' AND state <> 'idle'
ORDER BY dur DESC;
```

**Mitigación — procedimiento seguro de termination**

```sql
-- 1) intentar cancel (suave)
SELECT pg_cancel_backend(<pid>);
-- esperar 10s y verificar si la query salió
-- 2) si sigue activa, terminate (mata la conexión completa)
SELECT pg_terminate_backend(<pid>);
```

**Reglas**

- Antes de matar: capturar `query` y `application_name` en un incident log.
- Si proviene de la web app (gunicorn): considerar matar el worker en vez del backend PG (reinicia limpio).
- Nunca matar `autovacuum` o `walsender` salvo emergencia.

**Prevención**

- `statement_timeout` por rol: `ALTER ROLE app SET statement_timeout = '30s'`.
- `idle_in_transaction_session_timeout = '60s'`.

---

## 4. Bloat (dead tuples acumulados)

**Diagnóstico**

```sql
SELECT relname,
       n_live_tup,
       n_dead_tup,
       ROUND(100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0), 2) AS pct_dead,
       last_autovacuum, last_vacuum
FROM pg_stat_user_tables
ORDER BY pct_dead DESC NULLS LAST
LIMIT 20;
```

Con extensión `pgstattuple`:

```sql
SELECT * FROM pgstattuple('scans');
```

**Mitigación**

- Suave: `VACUUM (VERBOSE, ANALYZE) <tabla>`. No bloquea SELECTs.
- Si bloat >40% y la tabla es grande: `pg_repack` (zero-downtime; ver `extensions-evaluation.md`).
- Última instancia: `VACUUM FULL` (bloquea AccessExclusive — ventana de mantenimiento obligatoria).

**Prevención**

- Subir `autovacuum_vacuum_scale_factor` a 0.1 (default 0.2) para tablas grandes.
- Por tabla: `ALTER TABLE scans SET (autovacuum_vacuum_scale_factor = 0.05);`.

---

## 5. Disk full

**Síntoma**

```
ERROR: could not extend file "base/16384/12345": No space left on device.
```

**Mitigación urgente (orden!)**

1. **NO** intentar `VACUUM FULL` (necesita 2× espacio).
2. Liberar WAL archivado (si hay `archive_command` que ya transfirió): `pg_archivecleanup`.
3. `VACUUM` normal: no libera al SO pero detiene crecimiento.
4. `TRUNCATE` tablas temporales o de tests (rapidísimo, libera al SO).
5. Crecer disco (Render: upgrade tier o agregar volumen).
6. Tras espacio recuperado: `vacuumdb --analyze --all`.

**Prevención**

- Alerta a 70% / 80% / 90% de disco.
- Política de retention activa (ver `cleanup-policy-pack48.sql`).
- WAL: `archive_mode = on` + script de cleanup.

---

## 6. Replication broken / lag

**Síntoma**

```sql
SELECT now() - pg_last_xact_replay_timestamp() AS lag;
-- replica:
SELECT pid, state, sync_state, replay_lag, write_lag, flush_lag
FROM pg_stat_replication;
```

**Diagnóstico**

- Lag por **slot inactivo**: el primario retiene WAL.
- Lag por **CPU saturada** en replica.
- Lag por **conflicto recovery**: `hot_standby_feedback` desactivado + consulta larga en replica.

**Mitigación**

- Streaming roto temporal: rearmar con `pg_basebackup --slot=replica1 -R -D /var/lib/postgresql/data`.
- Logical replication rota: re-crear `SUBSCRIPTION`.

**Prevención**

- `wal_keep_size = 1GB` mínimo.
- `max_replication_slots = 10`.
- Monitor slot inactivo + auto-drop a las 24h.

---

## 7. Lost WAL (gap entre primario y replica)

**Síntoma**

```
ERROR: requested WAL segment 000000010000000A00000023 has already been removed.
```

**Mitigación**

- Si hay backup base reciente: `pg_basebackup` la replica desde cero.
- Si **no** hay base reciente: snapshot del primario + restore en replica.

**Prevención**

- WAL archive a S3 (`wal-g`, `barman`, `pgbackrest`).
- Slot replica garantiza retention pero exige monitoring.

---

## 8. Corrupted page

**Síntoma**

```
ERROR: invalid page in block 12345 of relation base/16384/12345
```

**Mitigación (ÚLTIMO recurso)**

1. **Parar** writes a la tabla afectada.
2. Identificar bloque: el mensaje da `block N`.
3. Dump filas vecinas a archivo aparte.
4. `SET zero_damaged_pages = on; VACUUM <tabla>;` — pone ceros en el bloque, pierde filas.
5. **Restaurar** desde backup si la data es crítica.
6. Reproducir e investigar root cause (hardware? bug PG? cosmic ray?).

**Prevención**

- `data_checksums = on` al `initdb` (Render lo hace).
- ECC RAM (managed).
- Backups testeados (ver `dr-drill-plan.md`).

---

## 9. Connection storm

**Síntoma**: `FATAL: sorry, too many clients already`.

**Mitigación**

```sql
-- ver quién está conectado
SELECT application_name, state, COUNT(*) AS n
FROM pg_stat_activity
GROUP BY 1, 2 ORDER BY n DESC;

-- matar idle in tx > 5min
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND now() - state_change > INTERVAL '5 minutes';
```

**Prevención**

- PgBouncer (`scripts/db/pgbouncer.ini`).
- `idle_in_transaction_session_timeout`.
- `application_name` consistente para identificar quién abre conexiones.

---

## 10. Sequence wrap / id collision

**Síntoma**: `INSERT` falla con `duplicate key value violates unique constraint "scans_pkey"` aunque la app cree que es id nuevo.

**Diagnóstico**

```sql
SELECT pg_get_serial_sequence('scans', 'id') AS seq,
       (SELECT last_value FROM <seq>) AS last,
       (SELECT MAX(id) FROM scans) AS max_id;
```

**Mitigación**

```sql
SELECT setval(pg_get_serial_sequence('scans','id'), (SELECT MAX(id) FROM scans));
```

**Prevención**

- `id BIGINT GENERATED BY DEFAULT AS IDENTITY` (PG10+, mejor que `SERIAL`).
- Backups con `pg_dump` preservan secuencias correctamente; restore con `--data-only` no.

---

## Helpers SQL

Centralizados en `scripts/db/monitoring-queries.sql`. Este playbook asume que el DBA tiene psql access al primario.

## Escalation

| Severidad | Página | Quién |
| --- | --- | --- |
| P0 (DB down / corrupted) | inmediata | DBA + Tech Lead |
| P1 (replication lag, disk >90%) | <15min | DBA |
| P2 (bloat, slow queries) | <4h | DBA |
| P3 (deprecation, refactor) | issue | DBA |

Ver `docs/db/on-call-playbook.md` para procedimiento completo.
