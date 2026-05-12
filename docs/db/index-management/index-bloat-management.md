# Index bloat management (Pack 48-H Round 6 · #155)

## Síntomas

- Tamaño índice >> esperado para n filas.
- Lectura/escritura más lenta.
- `pgstattuple` reporta alto `dead_tuple_percent`.

## Causas

- UPDATEs masivos en columnas indexadas.
- Long-running tx que retiene visibility horizon.

## Remediar

| Acción | Costo |
| --- | --- |
| `REINDEX INDEX CONCURRENTLY` | bajo, no bloquea writes |
| `REINDEX TABLE` | bloquea writes; ventana |
| `pg_repack -i` | sin bloqueo (si extensión disponible) |

## Argus

Plan ops mensual: detectar > 30% bloat en índices core → `REINDEX CONCURRENTLY`.

## Referencias

- `docs/db/bloat-management.md` (Round 4)
- `scripts/db/toolkits/pg_bloat_check.sql`
