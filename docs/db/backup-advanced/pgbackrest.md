# pgBackRest (Pack 48-H Round 5 · #145)

## Qué es

Herramienta backup/restore avanzada para PostgreSQL: **full**, **diff**, **incr**, compresión, cifrado, S3/Azure/GCS, PITR.

## Cuándo usar

- Self-managed clusters medianos/grandes.
- Necesidad de **incremental** eficiente vs `pg_dump` diario.

## Conceptos

| Concepto | Descripción |
| --- | --- |
| stanza | grupo lógico cluster |
| repo | almacenamiento backup |
| retention | full/diff/incr policies |
| archive-push | integración `archive_command` WAL |

## Flujo WAL archiving

`archive_command = 'pgbackrest --stanza=argus archive-push %p'`

## Argus Render

pgBackRest típicamente **no** aplica a Render managed (sin shell). Referencia para futura migración self-host.

## Referencias

- `docs/db/backup-advanced/wal-archiving.md`
- `docs/db/backup-strategy.md`
