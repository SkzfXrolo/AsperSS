# Consistent hashing (Pack 48-H Round 6 · #153)

## Problema

Hash modular (`hash(key) % N`) requiere remapear **casi todo** al cambiar N.

## Solución

Consistent hashing: ring 0..2^32 con nodos en posiciones; key cae en nodo siguiente clockwise. Adicionar/quitar nodos remapea **fracción 1/N**.

## Variantes

- **Virtual nodes** (vnodes): cada nodo físico ocupa K posiciones → balance.
- **Rendezvous hashing** (HRW): alternativa más simple.
- **Jump consistent hash** (Google): muy compacto para conteos crecientes.

## Argus

Sólo relevante en escenarios:

- Cache distribuido (Redis Cluster).
- Capa de routing custom hacia múltiples DB shards.

Para PG shards típico: rara vez vale la complejidad vs Citus.

## Referencias

- `docs/db/sharding/shard-rebalancing.md`
