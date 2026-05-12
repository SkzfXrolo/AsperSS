# psql tips (Pack 48-H Round 5 · #148)

## Atajos

- `\e` abre editor externo para query larga.
- `\timing` latencia cliente medida.
- `\copy` vs `COPY` (server-side).

## Seguridad

- `~/.pgpass` chmod 600.
- No dejar history sensible: `HISTFILE` desactivado en prod bastions.

## Referencias

- `docs/db/cheatsheet.md`
- `docs/db/ecosystem/cli-tools-comparison.md`
