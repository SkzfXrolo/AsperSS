# SQLite → PostgreSQL (Pack 48-H Round 6 · #160)

## Aplicabilidad Argus

Dev local usa SQLite (dual-mode via `_PH`); prod usa PG. Este doc detalla saltos a producción de bases SQLite si surge.

## Diferencias importantes

| Tema | SQLite | PG |
| --- | --- | --- |
| Types | type affinity (laxo) | estricto |
| `AUTOINCREMENT` | rowid | SERIAL/IDENTITY |
| Booleans | INTEGER 0/1 | BOOLEAN |
| Dates | TEXT/INTEGER | TIMESTAMPTZ |
| Foreign keys | off por default | enforced |
| Concurrencia | una writer | multi-writer MVCC |

## Migración

- `pgloader` también soporta SQLite.
- Convertir `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGSERIAL`.

## Argus particular

`_PH` placeholder maneja `?` vs `%s`. Migration full a PG requiere consolidar **toda** la lógica vía Alembic (ver Pack 49 plan).

## Referencias

- `docs/db/schema-pack48.md`
- `docs/db/pack49-migration-plan/overview.md`
