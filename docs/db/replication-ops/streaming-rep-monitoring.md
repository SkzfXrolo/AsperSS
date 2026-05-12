# Streaming replication monitoring (Pack 48-H Round 6 · #154)

## Vistas clave

```sql
SELECT pid, usename, application_name, client_addr, state, sync_state,
       pg_wal_lsn_diff(sent_lsn, write_lsn)  AS write_lag_bytes,
       pg_wal_lsn_diff(sent_lsn, flush_lsn)  AS flush_lag_bytes,
       pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag_bytes,
       write_lag, flush_lag, replay_lag
FROM pg_stat_replication;
```

En standby:

```sql
SELECT pg_is_in_recovery(), pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn(),
       now() - pg_last_xact_replay_timestamp() AS replay_age;
```

## Slots

```sql
SELECT slot_name, plugin, slot_type, active, restart_lsn,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained
FROM pg_replication_slots;
```

## Alertas sugeridas

- `replay_lag_bytes > 256 MB` → warn.
- `replay_age > 60s` → warn (depende SLO).
- `slot.retained > 8 GB` → P0 (riesgo disk full).

## Argus

Render: visibilidad limitada; pedir métricas vía soporte si réplica gestionada.

## Referencias

- `scripts/db/toolkits/pg_replication_lag.sql`
