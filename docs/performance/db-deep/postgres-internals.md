# Postgres Internals (Deep)

## MVCC

- Cada fila mantiene visibilidad por `xmin/xmax`.
- Lecturas no bloquean escrituras; costo: tuples muertas y bloat.
- Impacto: si autovacuum no acompaña, suben latencias por heap scans.

## WAL (Write-Ahead Log)

- Todo cambio se escribe primero en WAL.
- `checkpoint` sincroniza paginas sucias; si es agresivo, genera spikes de IO.
- Ajustes clave: `max_wal_size`, `checkpoint_completion_target`, `wal_compression`.

## Vacuum y Autovacuum

- `VACUUM` recupera espacio reutilizable y mantiene estadisticas de visibilidad.
- `VACUUM FULL` bloquea y reescribe tabla (usar solo en ventanas controladas).
- Tunear thresholds por tablas calientes para evitar bloat cronico.

## Buffer cache

- `shared_buffers` guarda paginas de datos/index en RAM.
- Hit ratio bajo + IO alto = working set mayor que memoria efectiva.
- Medir con `pg_stat_bgwriter`, `pg_stat_io`, `pg_statio_user_tables`.

## Checklist operativo Argus

- Monitorear bloat por tabla/index semanalmente.
- Revisar lag de autovacuum y dead tuples.
- Correlacionar p99 de endpoints con checkpoints y WAL fsync.
