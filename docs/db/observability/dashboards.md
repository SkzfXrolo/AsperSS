# Grafana dashboards (DB deep) (Pack 48-H Round 5 · #138)

Extiende `docs/db/dashboards-spec.md` (Round 3) con paneles adicionales y notas de implementación.

## Dashboard: `argus-db-overview-v2`

| Panel | Query / métrica | Objetivo |
| --- | --- | --- |
| Connections stacked | `numbackends` por `application_name` | detectar pool leak |
| States pie | active/idle/idle in tx | salud sesiones |
| TPS | deriv(`xact_commit`) | carga |
| Rollback rate | `xact_rollback / (commit+rollback)` | bugs app |
| Cache hit | fórmula blks_hit | memoria |
| Temp files | `temp_bytes` | sorts spills |
| Checkpoints | timed vs requested | tuning `max_wal_size` |
| Replication lag | lag seconds | réplica |
| Top 5 tables size | `pg_database_size` + top rel | capacity |
| WAL rate | deriv WAL bytes | anomalías |

## Dashboard: `argus-db-queries`

- Tabla bar: `pg_stat_statements` top por `total_time`.
- Histograma: `mean_exec_time` distribution (bucketize en recording rule).

## Dashboard: `argus-db-locks`

- `pg_locks` waiting count.
- Table of blockers (`pg_blocking_pids`).

## Variables Grafana

- `datasource` Prometheus.
- `cluster` (prod/staging).
- `namespace` si K8s.

## JSON

Mantener JSON exportado en repo infra (fuera de `docs/db`); aquí sólo spec para que platform team genere.

## Referencias

- `docs/db/pgbadger-guide.md`
- `docs/db/observability/log-analysis.md`
