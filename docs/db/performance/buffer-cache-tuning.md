# Buffer cache tuning (Pack 48-H Round 5 · #141)

## Concepto

`shared_buffers` cachea páginas 8KB en RAM. OS cache también cachea archivos.

## Heurísticas

| Entorno | shared_buffers guía |
| --- | --- |
| OLTP pequeño | 25% RAM |
| Grande RAM (>64GB) | 8–32GB a menudo suficiente; medir hit ratio |

## Métrica clave

Cache hit:

```sql
SELECT sum(blks_hit)*1.0 / NULLIF(sum(blks_hit+blks_read),0) AS ratio
FROM pg_stat_database;
```

Target típico **> 0.99** OLTP; si menor, revisar RAM, queries seq scan, cold start.

## work_mem

No es buffer cache compartido, pero afecta sorts/hash en queries — tunear por rol/reporting.

## Argus managed

Render no permite tune fino; enfocarse en queries + índices + pool.

## Referencias

- `docs/db/observability/key-metrics.md`
- `docs/db/bloat-management.md`
