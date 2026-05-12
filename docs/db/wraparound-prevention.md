# Transaction ID wraparound prevention (Pack 48-H Round 4 · #113)

## El problema

PostgreSQL identifica filas con un **xmin/xmax** de **32 bits** (XID). Cuando llega a ~2 mil millones, **da vuelta** ("wraparound"). Si no hay un VACUUM FREEZE previo de filas viejas, los xmin viejos parecen del futuro y **los datos se vuelven invisibles**. Es uno de los pocos casos donde PG corrompe lógicamente la DB.

A modo de defensa, PG **detiene escrituras** cuando se acerca al límite:

```
ERROR: database is not accepting commands to avoid wraparound data loss in database "argus_prod"
HINT: Stop the postmaster and vacuum that database in single-user mode.
```

## Por qué Argus debe preocuparse

- `ai_decisions_log`, `scans`, `plugin_violations` reciben **inserts constantes**. A 30k inserts/día × 100 clientes × 365 días = ~1.1 mil millones XIDs/año. Llegamos cerca del wraparound en 2-3 años sin VACUUM agresivo.
- Autovacuum protege automáticamente, **pero** se puede atascar si hay long-running transactions, slots inactivos, o tablas excluidas del autovacuum.

## Monitoreo (semanal, hard)

```sql
-- Edad por DB (xact_id "freezeado")
SELECT datname,
       age(datfrozenxid)                      AS xid_age,
       2^31 - age(datfrozenxid)               AS xids_remaining,
       ROUND(100.0 * age(datfrozenxid) / (2^31), 2) AS pct_used
FROM pg_database
ORDER BY xid_age DESC;
```

- Acción a >50%: investigar.
- Acción a >75%: hoja roja, plan freezing.
- Acción a >90%: P0.

Por tabla:

```sql
SELECT c.relname,
       age(c.relfrozenxid)                                AS xid_age,
       pg_size_pretty(pg_total_relation_size(c.oid))      AS size,
       n_live_tup, n_dead_tup, last_autovacuum, last_vacuum
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
WHERE c.relkind = 'r' AND n.nspname='public'
ORDER BY age(c.relfrozenxid) DESC
LIMIT 30;
```

## Settings clave

```
autovacuum_freeze_max_age      = 200000000   -- default, OK para empezar
vacuum_freeze_table_age        = 150000000   -- forzar FREEZE manual a >150M
vacuum_freeze_min_age          = 50000000    -- congelar xmin <50M
autovacuum_multixact_freeze_max_age = 400000000  -- multixacts
```

Para tablas críticas, **bajar** estos por tabla:

```sql
ALTER TABLE ai_decisions_log SET (autovacuum_freeze_max_age = 100000000);
ALTER TABLE scans            SET (autovacuum_freeze_max_age = 100000000);
```

Razón: vacuumamos más a menudo, pero en pedazos pequeños (no un evento masivo de "aggressive autovacuum" al final).

## Causas comunes de starvation

| Causa | Mitigación |
| --- | --- |
| Transacción de larga duración | matar pid; `idle_in_transaction_session_timeout` |
| Replication slot inactivo | `pg_replication_slots.active=false` + WAL retenido + xmin retenido |
| `vacuum_defer_cleanup_age` muy alto | bajar a 0 (default OK) |
| Tabla con `autovacuum_enabled = off` | revisar y corregir |
| Prepared transactions huérfanas (`PREPARE TRANSACTION`) | `ROLLBACK PREPARED` |

```sql
-- detectar tx muy viejas
SELECT pid, age(backend_xmin) AS xmin_age, backend_xid, state, query
FROM pg_stat_activity
WHERE backend_xmin IS NOT NULL
ORDER BY xmin_age DESC LIMIT 10;

-- detectar slots problemáticos
SELECT slot_name, active, age(xmin) AS xmin_age FROM pg_replication_slots
ORDER BY xmin_age DESC;
```

## Procedimiento de emergencia

### Si estamos cerca del wraparound (P0)

1. **Stop writes**: aplicación en mantenimiento.
2. **Identificar bloqueador**: tx vieja, slot inactivo, prepared tx.
3. **Resolver**:
   - Matar tx con `pg_terminate_backend()`.
   - Drop slot inactivo: `SELECT pg_drop_replication_slot('nombre');`.
   - `ROLLBACK PREPARED 'gid'` si es prepared tx.
4. **VACUUM FREEZE manual** de las tablas más viejas:
   ```sql
   VACUUM (FREEZE, VERBOSE, ANALYZE) ai_decisions_log;
   ```
   No bloquea SELECTs; sí compite por IO.
5. **Reintentar writes** y monitorear `pg_database.datfrozenxid`.

### Si PG ya rechazó writes

1. Detener postmaster (Render: pedir maintenance window urgent).
2. `postgres --single -D /data argus_prod` en single-user mode.
3. `VACUUM FREEZE;` (puede tardar horas).
4. Reiniciar normal.

## Plan preventivo Argus

| Acción | Frecuencia |
| --- | --- |
| Query `pg_database` xid_age | semanal en Grafana |
| Alerta xid_age > 1 mil millones | crítica |
| Por-tabla `relfrozenxid` review | mensual |
| Manual `VACUUM FREEZE` off-peak | trimestral, tabla más vieja |
| Audit de slots inactivos | semanal |

## Particionado ayuda

Tablas particionadas tienen una **partición congelable a la vez**: cada `DROP PARTITION` elimina ~30 días de XIDs sin tener que `VACUUM` filas viejas. Por eso `scans` particionada mensualmente nunca acumula XIDs viejos comparado con la versión monolítica.

(Ver `partitioning-design.md` #89.)

## Test sintético

Para validar el plan, en staging:

```sql
-- simular alto consumo de XID (NO en prod)
DO $$
BEGIN
  FOR i IN 1..1000000 LOOP
    EXECUTE 'BEGIN; INSERT INTO test_xid SELECT 1; COMMIT;';
  END LOOP;
END $$;

-- ver consumo
SELECT age(datfrozenxid), txid_current() FROM pg_database WHERE datname=current_database();
```

## Métricas Grafana sugeridas

Panel: `xid_age_pct` con thresholds:

```
- green:  < 25%
- yellow: 25-50%
- orange: 50-75%
- red:    > 75%
```

Ver `dashboards-spec.md` para template.

## Referencias

- PG Manual §25 "Routine Database Maintenance Tasks".
- `bloat-management.md` (#114) — pg_repack también ayuda.
- `autovacuum-tuning.md` (#115) — tuning del autovacuum.
