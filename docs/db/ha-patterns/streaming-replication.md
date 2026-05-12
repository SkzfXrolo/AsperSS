# Streaming replication (physical) (Pack 48-H Round 5 · #136)

## Definición

**Streaming replication** replica registros WAL byte-a-byte a una **standby** en caliente (hot standby). Es el pilar de HA clásico en PostgreSQL self-managed.

## Modos

| Modo | Descripción |
| --- | --- |
| Async | Standby puede ir atrasada; primario nunca espera ACK del standby. |
| Sync | Primario espera flush en standby antes de commit (ver `synchronous-replication.md`). |

## Roles

- **Primary**: acepta writes.
- **Standby / Replica**: read-only (`hot_standby = on`); recibe WAL vía protocolo replication.

## Checkpoints operativos

```sql
SELECT application_name, state, sync_state, pg_wal_lsn_diff(sent_lsn, write_lsn) AS write_lag,
       pg_wal_lsn_diff(sent_lsn, flush_lsn) AS flush_lag,
       pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag
FROM pg_stat_replication;
```

En standby:

```sql
SELECT pg_is_in_recovery();
SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn();
```

## Promoción (failover)

- `pg_ctl promote` o API Patroni/repmgr.
- **Timeline** incrementa; clients deben reconectar al nuevo primary.

## Argus en Render

Render managed puede ofrecer read replicas como producto; no es streaming self-managed. Ver `docs/db/read-replicas-design.md` y `render-runbook.md`.

## Cuándo preferir streaming vs lógica

- **Failover rápido + réplica idéntica** → streaming.
- **Subset tablas / major upgrade** → lógica.

## Referencias

- `docs/db/ha-patterns/synchronous-replication.md`
- `docs/db/ha-patterns/failover-strategies.md`
