# Zero downtime changes (Pack 48-H Round 6 · #165)

## Principios

1. App debe poder correr con schema **viejo y nuevo** simultáneamente.
2. Schema cambia primero; código después.
3. Drop **siempre** dos releases después de dejar de usar.

## Patrón rename column

| Paso | DB | App |
| --- | --- | --- |
| 1 | add `new_name` + trigger sync | read old, write both |
| 2 | backfill old→new | n/a |
| 3 | read new, write both | switch reads |
| 4 | drop trigger, drop old | drop writes a old |

## Argus

Aplicar para renames y normalizaciones futuras.

## Referencias

- `docs/db/cookbook/large-table-alterations.md`
