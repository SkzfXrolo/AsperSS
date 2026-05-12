# Incremental backups (Pack 48-H Round 5 · #145)

## Tipos

| Tipo | Herramienta típica | Ventaja |
| --- | --- | --- |
| pg_dump custom + diff externo | scripts | simple |
| pgBackRest incremental | nativo | rápido |
| Filesystem snapshots (ZFS/LVM) | storage | RTO bajo |

## Plan retención

- Full semanal + incr diarios + WAL continuo.
- Validar restore **incr** trimestralmente.

## Argus

Hasta self-host: `pg_dump` custom diario + weekly full a S3 (`backup-automation.sh`).

## Referencias

- `docs/db/dr-drill-plan.md`
