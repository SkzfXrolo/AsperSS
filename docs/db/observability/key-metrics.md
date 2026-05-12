# Top 20 PostgreSQL metrics (Pack 48-H Round 5 · #138)

Métricas clave para `postgres_exporter` + Grafana/Prometheus. Nombres orientativos; mapear al exporter real.

| # | Métrica / query base | Por qué importa |
| --- | --- | --- |
| 1 | `pg_stat_database_numbackends` | Saturación conexiones vs `max_connections` |
| 2 | `pg_stat_activity_count by state` | idle in transaction, active, idle |
| 3 | `pg_stat_activity_max_tx_age_seconds` | tx largas = locks/bloat |
| 4 | `pg_locks_waiting_count` | contención |
| 5 | `pg_stat_database_blks_hit_ratio` | cache hit (buffer) |
| 6 | `pg_stat_bgwriter_buffers_backend_fsync` | presión checkpointer |
| 7 | `pg_database_size_bytes` | crecimiento disco |
| 8 | `pg_stat_user_tables_n_dead_tup` | necesidad vacuum |
| 9 | `pg_stat_user_tables_last_autovacuum` | starvation autovacuum |
| 10 | `pg_stat_user_indexes_idx_scan` | índices no usados |
| 11 | `pg_stat_user_tables_seq_scan` | seq scans tablas grandes |
| 12 | `pg_stat_statements_mean_time_ms` | queries lentas |
| 13 | `pg_stat_statements_total_time_ms` | costo acumulado |
| 14 | `pg_replication_lag_seconds` | DR/replica health |
| 15 | `pg_replication_slots_retained_wal_bytes` | riesgo disco por CDC |
| 16 | `pg_wal_generation_bytes_per_sec` | picos anómalos |
| 17 | `pg_stat_database_xact_commit_rollbacks` | ratio rollback |
| 18 | `pg_stat_database_conflicts` | conflictos recovery réplica |
| 19 | `pg_settings_pending_restart` | config drift no aplicada |
| 20 | `pg_database_age_datfrozenxid` | riesgo wraparound |

## Queries de apoyo (referencia)

Ver `scripts/db/monitoring-queries.sql` y `docs/db/wraparound-prevention.md`.

## Cardinalidad

Evitar labels altos-cardinality (ej. `query` completa) en Prometheus; usar fingerprint o top-N rotativo.

## Referencias

- `docs/db/observability/alert-thresholds.md`
- `docs/db/dashboards-spec.md` (Round 3)
