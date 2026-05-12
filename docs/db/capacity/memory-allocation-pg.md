# Memory allocation PG (Pack 48-H Round 6 · #161)

## Áreas

| Área | Propósito |
| --- | --- |
| `shared_buffers` | cache páginas compartido |
| `work_mem` | por sort/hash op |
| `maintenance_work_mem` | VACUUM, CREATE INDEX |
| `wal_buffers` | WAL antes flush |
| `effective_cache_size` | hint al planner (no aloca) |
| `temp_buffers` | tablas temporales sesión |

## Argus (tier Standard ejemplo)

```text
shared_buffers          ≈ 1 GB     (25% de 4 GB)
work_mem                ≈ 16-32 MB (por consulta concurrente)
maintenance_work_mem    ≈ 256 MB
effective_cache_size    ≈ 3 GB
wal_buffers             ≈ 16 MB
```

Render maneja parte; lo que NO podemos tunear, dimensionamos via tier.

## Referencias

- `docs/db/performance/buffer-cache-tuning.md`
