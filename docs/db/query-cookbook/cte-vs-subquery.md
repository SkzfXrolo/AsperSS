# CTE vs subquery (Pack 48-H Round 6 · #156)

## Diferencias clave

| Tema | CTE (`WITH`) | Subquery |
| --- | --- | --- |
| Optimization fence | Pre-PG12: sí. PG12+: inlinable por default | siempre inlinable |
| Legibilidad | mejor en queries largas | compacta |
| Materialización forzada | `WITH ... AS MATERIALIZED` PG12+ | n/a |
| Recursividad | `WITH RECURSIVE` | no directo |

## Recomendación

- PG12+ usar CTE para claridad sin penalty.
- `MATERIALIZED` cuando se quiere evitar recompute en subqueries dependientes.

## Argus

Reportes complejos → CTE etapas (`reports/*.sql`).

## Referencias

- `docs/db/postgres-topics/recursive-cte.md`
