# CLI tools comparison (Pack 48-H Round 5 · #148)

| Tool | Uso principal | Argus |
| --- | --- | --- |
| `psql` | interactivo + scripting | default |
| `pgbench` | load testing | `stress-test/pgbench-scenarios.md` |
| `pg_dump`/`pg_restore` | backups lógicos | runbook |
| `pg_basebackup` | físico | self-host |
| `pg_receivewal` | WAL tooling | HA avanzada |
| `pg_isready` | healthcheck | k8s probes |
| `vacuumdb` | mantenimiento batch | ops |
| `reindexdb` | reindex | ventana |

## Recomendación

Mantener scripts en `scripts/db/**` versionados; evitar one-off en laptops.

## Referencias

- `docs/db/cheatsheet.md`
