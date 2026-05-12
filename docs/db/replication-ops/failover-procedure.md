# Failover procedure (Pack 48-H Round 6 · #154)

## Pre-cheques

- Confirmar primary realmente caído (no falso positivo).
- Verificar mejor réplica candidate: menor lag, salud OK.
- Notificar canal #ops + Incidente.

## Pasos

1. **Fence** primary (si posible): cortar tráfico (DNS, proxy).
2. `pg_ctl promote` o API managed.
3. Validar timeline incremental (`pg_controldata` / logs).
4. Update connection strings / proxy (PgBouncer reconfig).
5. App health checks.
6. Reapuntar réplicas restantes al nuevo primary (`primary_conninfo`).
7. Crear backup fresco inmediatamente post-failover.
8. Postmortem.

## RTO target

- Auto (Patroni): 1-5 min.
- Manual managed: 15-45 min.

## Argus

Render: failover suele requerir interacción con soporte. Documentar tickets P0.

## Referencias

- `docs/db/ha-patterns/failover-strategies.md`
- `docs/db/replication-ops/failback-procedure.md`
