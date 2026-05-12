-- scripts/db/toolkits/pg_replication_lag.sql · Pack 48-H Round 6 · #159
-- Replication lag desde primary y desde standby.

-- Desde primary:
SELECT application_name, client_addr, state, sync_state,
       pg_wal_lsn_diff(pg_current_wal_lsn(), sent_lsn)   AS sent_lag_bytes,
       pg_wal_lsn_diff(sent_lsn, flush_lsn)              AS flush_lag_bytes,
       pg_wal_lsn_diff(sent_lsn, replay_lsn)             AS replay_lag_bytes,
       write_lag, flush_lag, replay_lag
FROM pg_stat_replication;

-- Slots y WAL retenido:
SELECT slot_name, plugin, slot_type, active,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained_wal
FROM pg_replication_slots;

-- Desde standby (correr en réplica):
SELECT pg_is_in_recovery() AS is_replica,
       pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn(),
       now() - pg_last_xact_replay_timestamp() AS replay_age;
