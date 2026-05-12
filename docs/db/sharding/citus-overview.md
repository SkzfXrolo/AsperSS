# Citus overview (Pack 48-H Round 6 · #153)

## Qué es

Extensión PostgreSQL (Microsoft/EDB) que **distribuye tablas** entre nodos worker con coordinator. SQL casi transparente.

## Conceptos

| Concepto | Rol |
| --- | --- |
| Coordinator | recibe queries, planifica fan-out |
| Workers | nodos con shards |
| Distributed table | particionada por shard key |
| Reference table | replicada en todos los workers |
| Colocation | tablas con mismo shard key co-localizadas |

## Cuándo

- Multi-tenant SaaS grande (Citus el caso canónico).
- Workloads analytics distribuidos.

## Operación

- DDL via coordinator.
- Failover por worker más complejo que single PG.

## Render

Citus **no** está disponible managed Render por default. Self-host requerido.

## Argus

Pre-mature Pack 48. Re-evaluar si >100 tenants enterprise + heavy DW.

## Referencias

- Citus docs
- `docs/db/sharding/argus-sharding-when.md`
