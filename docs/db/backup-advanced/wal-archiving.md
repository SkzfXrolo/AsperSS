# WAL archiving strategies (Pack 48-H Round 5 · #145)

## Objetivo

Habilitar **PITR** (recovery a punto en tiempo) además de full backups.

## Parámetros

```text
wal_level = replica (o logical si CDC)
archive_mode = on
archive_command = '... push %p ...'
archive_timeout = 300s   -- forzar rotate si bajo tráfico
```

## Destinos

| Destino | Pros |
| --- | --- |
| S3 con `wal-g` / pgBackRest | durable, barato |
| NFS | simple | fragilidad locking |
| Local disk | dev only |

## Monitoreo

- Fallos `archive_command` → disk WAL llena → DB stop.
- Alertas si `archived_count` no incrementa.

## Argus

Render: delegar PITR a feature proveedor; offsite WAL propio puede ser imposible sin acceso FS.

## Referencias

- `docs/db/backup-advanced/incremental-backups.md`
