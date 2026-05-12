# DB sizing formulas (Pack 48-H Round 6 · #161)

## Storage por tabla (estimado)

```
size ≈ rows * (sum(col_avg_bytes) + 24 bytes header) + indexes_overhead
```

Header tuple ≈ 24 bytes; TOAST agrega para >2KB.

## Índice B-tree

```
index_size ≈ rows * (key_bytes + 8) * fill_factor_inv
```

`fill_factor` default 90% para btree (~1.1x).

## RAM mínima recomendada

```
shared_buffers ≈ 25% RAM
work_mem * max_connections ≈ resto (cuidado)
```

## Conexiones

Ver `connection-pool-sizing.md`.

## Argus

Plantilla en `cost-forecast.md` Round 3 incluye proyección.

## Referencias

- `docs/db/capacity/memory-allocation-pg.md`
