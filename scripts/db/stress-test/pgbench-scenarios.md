# pgbench scenarios (Pack 48-H Round 5 · #150)

> Documentación para stress tests. Ejecutar **sólo** en DB no productiva.

## Instalación dataset

```bash
pgbench -i -s 50 --foreign-keys $DATABASE_URL_NONPROD
```

`-s` scale factor (tablas `pgbench_*`).

## Escenarios

| ID | Comando | Objetivo |
| --- | --- | --- |
| S1 | `pgbench -c 10 -j 2 -T 300 -M prepared $URL` | TPS baseline OLTP simple |
| S2 | `pgbench -c 50 -j 4 -T 120 $URL` | saturación CPU |
| S3 | custom script con scans simulados | requiere schema Argus seed |

## Custom script (idea)

`/scripts/db/stress-test/custom.sql` (futuro) con queries copiadas de `explain-templates.sql`.

## Métricas recolectar

- `pg_stat_statements` reset antes/después.
- CPU/RAM/disk latency del host.

## Referencias

- `scripts/db/stress-test/connection-storm.sql`
- `scripts/db/bench/run-bench.sh`
