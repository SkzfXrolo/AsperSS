# Migration rollback strategy (Pack 48-H Round 6 · #164)

## Niveles

1. **Reversible Alembic**: `downgrade -1` (preferido para changes additive).
2. **Forward-fix**: emitir migration nueva que corrige.
3. **Restore backup**: último recurso.

## Reglas

- DROP de columnas/tablas: **nunca** en la release que dejan de usarse; 2 releases mínimo.
- Backfills destructivos: backup + dry-run + ventana.

## Argus

Documentar plan rollback en PR description de cada migration; sin esto, no merge.

## Referencias

- `docs/db/migration-tooling-deep.md` (rollback rules table)
- `docs/db/cookbook/data-backfills.md`
