# COUNT optimization (Pack 48-H Round 6 · #156)

## Problema

`SELECT count(*) FROM big_table` requiere full scan (MVCC).

## Alternativas

| Alternativa | Cuándo |
| --- | --- |
| `pg_class.reltuples` (estimado) | UI con número aproximado |
| `pg_stat_user_tables.n_live_tup` | similar |
| Contadores materializados (trigger) | conteo exacto frecuente |
| Conteo aproximado HyperLogLog (extensión) | distintos valores |
| EXPLAIN estimate | one-off |

## Argus

- Footer "≈ 1.2M scans" usa `reltuples`.
- Conteo exacto reporte mensual: programar nocturno.

## Patrón estimate seguro

```sql
SELECT reltuples::bigint AS approx FROM pg_class WHERE relname = 'scans';
```

## Referencias

- `docs/db/anti-patterns.md`
