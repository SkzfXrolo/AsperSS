# Active-active multi-region (Pack 48-H Round 5 · #139)

## Desafíos

| Desafío | Detalle |
| --- | --- |
| Conflictos escritura | Dos primarios → mismas filas divergentes |
| Latencia commit | Sync cross-region mata throughput |
| Secuencias / UUID | Colisiones si no global uniqueness |
| Leyes datos | Residencia en jurisdicción |
| Observabilidad | Lag + skew entre regiones |

## Patrones viables

1. **Partition por tenant/region** (cada región escribe subset sin overlap).
2. **CRDB/Citus** (otra tecnología) — fuera de scope PG puro.
3. **Spanner-like** — no aplica.

## PostgreSQL puro

Active-active **no recomendado** Argus salvo partición estricta de claves + disciplina operativa extrema.

## Alternativa pragmática

- Active-passive + **read replicas** regionales para dashboards tolerantes a lag.
- **Edge cache** para lecturas derivadas (no DB writes).

## Referencias

- `docs/db/logical-replication/conflict-resolution.md`
- `docs/db/multi-region-deep/latency-tradeoffs.md`
