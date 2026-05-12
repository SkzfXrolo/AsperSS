# Alert thresholds (Pack 48-H Round 5 · #138)

Valores iniciales; ajustar con baseline real. Severidad: P0 crítico, P1 alto, P2 warning.

| Alerta | Condición sugerida | Sev |
| --- | --- | --- |
| Connections high | `numbackends / max_connections > 0.85` 5m | P1 |
| Idle in transaction | cualquier sesión `idle in transaction` > 60s | P1 |
| Long query | `now-query_start > 5 min` y `state=active` | P2 |
| Replication lag | `replay_lag > 60s` | P1 |
| Slot WAL retained | `retained_wal > 8GB` | P0 |
| Cache hit low | `blks_hit/(blks_hit+blks_read) < 0.95` 30m | P2 |
| Dead tuples spike | `dead_pct > 30%` en tabla top size | P2 |
| Disk usage | `database_size > 80%` filesystem | P1 |
| Autovacuum stale | `last_autovacuum` > 7d en tabla hot | P2 |
| Wraparound risk | `age(datfrozenxid) > 200M` | P0 |
| Failed logins | spike auth errors | P1 |
| Checkpoint too frequent | `checkpoints_req/time > checkpoints_timed` | P2 |
| Lock waits | `count waiting locks > 10` | P1 |
| TPS drop | `tps < 0.5 * baseline_7d` 15m | P2 |
| Error rate app | `db_timeout_ratio > 1%` 5m | P1 |

## Runbook link

Cada alerta debe mapear a sección en `on-call-playbook.md`.

## Anti-alert fatigue

- Usar `for: 5m` en Prometheus.
- Page sólo P0/P1.

## Referencias

- `docs/db/observability/key-metrics.md`
- `docs/db/observability/dashboards.md`
