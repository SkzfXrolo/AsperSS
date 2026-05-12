# Barman (Pack 48-H Round 5 · #145)

## Qué es

Suite Python de 2ndQuadrant/EDB para backups físicos + WAL management + `barman-cli` restore.

## Fortalezas

- Catalogación de backups.
- `receive-wal` daemon.
- Integración hook pre/post backup.

## Comparación rápida vs pgBackRest

| Aspecto | Barman | pgBackRest |
| --- | --- | --- |
| Incremental | limitado vs pgBackRest moderno | fuerte |
| Ecosystem | maduro Python shops | muy popular ops |

## Argus

Self-host only. Combinar con `backup-automation.sh` Round 2 para offsite complementario.

## Referencias

- `docs/db/backup-advanced/pgbackrest.md`
