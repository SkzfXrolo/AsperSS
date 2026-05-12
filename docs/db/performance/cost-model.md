# PostgreSQL cost model (Pack 48-H Round 5 · #141)

## Idea

El planner estima **costo abstracto** (unidades arbitrarias) usando estadísticas (`pg_stats`) y parámetros `cpu_*`, `seq_page_cost`, `random_page_cost`.

## Parámetros sensibles

| Parámetro | Efecto |
| --- | --- |
| `seq_page_cost` | favorece o penaliza seq scan |
| `random_page_cost` | index scan vs seq (SSD → bajar respecto HDD clásico) |
| `cpu_tuple_cost` / `cpu_index_tuple_cost` | nested loops |

## SSD tuning típico

```text
random_page_cost = 1.1
seq_page_cost = 1.0
```

(Validar con benchmarks propios.)

## Estadísticas

- `ANALYZE` tras cargas masivas.
- `ALTER TABLE ... ALTER COLUMN ... SET STATISTICS 1000` en columnas críticas de filtros.

## Por qué importa Argus

Mal `random_page_cost` en SSD puede forzar seq scans innecesarios o viceversa.

## Herramientas

- `EXPLAIN (SETTINGS)` muestra costos y settings activos.

## Referencias

- `docs/db/performance/query-optimization.md`
