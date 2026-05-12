# Large table alterations (Pack 48-H Round 6 · #165)

## Operaciones seguras

| Op | Coste | Estrategia |
| --- | --- | --- |
| `ADD COLUMN nullable` | ms | OK online |
| `ADD COLUMN NOT NULL DEFAULT const` (PG11+) | ms | OK |
| `ADD COLUMN NOT NULL DEFAULT now()` | full rewrite | ventana |
| `ALTER COLUMN TYPE` (compat) | suele rewrite | ventana o dual-col |
| `DROP COLUMN` | ms | OK (siempre tras desuso) |
| `ADD CONSTRAINT NOT VALID` + `VALIDATE` | bajo | preferido |

## Reglas

- `SET lock_timeout` antes de cada ALTER.
- Si ALTER puede tardar > N segundos: ventana o estrategia dual.

## Argus

Documentar duración estimada en PR description para tablas > 5M filas.

## Referencias

- `docs/db/anti-patterns.md`
