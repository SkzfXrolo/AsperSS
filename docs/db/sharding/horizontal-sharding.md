# Horizontal sharding (Pack 48-H Round 6 · #153)

## Concepto

Distribuir **filas de la misma tabla** en **N nodos** según shard key.

## Shard keys candidatos Argus

| Key | Pros | Cons |
| --- | --- | --- |
| `company_id` | natural multi-tenant, locality | hot shards si tenant grande |
| `hash(company_id)` | balance | join cross-shard caro |
| `created_at` | temporal pruning | hot shard "actual mes" |
| `region` | data sovereignty | mover tenants entre regiones |

## Patrones de routing

| Patrón | Descripción |
| --- | --- |
| App-aware | app calcula shard y conecta directo |
| Proxy (Citus/PgCat) | proxy transparente |
| Service per shard | endpoint propio por shard |

## Cross-shard queries

- Fan-out + merge en app.
- Materializar agregados globales en tabla "results".

## Cuándo

Cuando read replicas + vertical sharding + partitioning **no alcanzan**. Pack 48 NO.

## Referencias

- `docs/db/sharding/citus-overview.md`
- `docs/db/argus-sharding-when.md`
