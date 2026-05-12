# Patroni HA management (Pack 48-H Round 5 · #136)

## Qué es Patroni

Patroni orquesta PostgreSQL en cluster: **leader election**, **failover automático**, **reconfiguración** de replicas y integración con HAProxy/PgBouncer.

## Componentes

| Pieza | Rol |
| --- | --- |
| DCS | etcd, Consul, ZooKeeper, Kubernetes Endpoints |
| Patroni agent | Corre en cada nodo PG |
| Callbacks | Scripts en promote/restart |
| REST API | Health checks |

## Flujo failover (simplificado)

1. Primary deja de hacer heartbeats en DCS.
2. Patroni candidatos compiten por lock.
3. Ganador `pg_ctl promote`.
4. Rewire replicas `primary_conninfo`.
5. Actualizar leader key para clientes.

## Integración PgBouncer

- `PAUSE` en switchover opcional.
- Reconfig dinámica de `default_pool` hacia nuevo primary.

## Argus

**Roadmap** si se sale de Render a K8s: Patroni + 3 AZ + sync local.

## Operación

- Versionar `bootstrap` YAML.
- Pruebas trimestrales de failover (`dr-drill-plan.md`).
- Alertas: `patroni_cluster_has_no_leader`.

## Referencias

- Patroni GitHub README
- `docs/db/connection-pool.md`
