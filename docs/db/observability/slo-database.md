# Database SLOs (Pack 48-H Round 5 · #138)

## Definición

**SLO** = objetivo medible de confiabilidad/latencia sobre una ventana (30 días). Se apoya en **SLI** (indicador) y se gestiona con **error budget**.

## SLIs recomendados Argus

| SLI | Definición | Fuente |
| --- | --- | --- |
| Availability | % requests API que obtienen respuesta DB OK (no timeout) | app metrics + PG |
| Latency p95 | p95 tiempo query panel principal | `pg_stat_statements` + APM |
| Durability | % commits que sobreviven failover test mensual | DR drill |
| Freshness analytics | `now()-max(created_at)` scans < 5 min | SQL cron |

## SLO ejemplo (borrador)

- **Availability** 99.9% mensual (máx ~43 min downtime).
- **p95** lecturas panel < 200 ms (excluyendo cold start).
- **Replication lag** p99 < 30 s (si réplica existe).

## Error budget

Si se quema budget:

- Congelar features no críticas.
- Priorizar índices, pool tuning, cache.

## Multi-tenant fairness

Opcional: SLO **por decil de company size** para no penalizar tenants pequeños por vecinos ruidosos (sharding futuro).

## Referencias

- `docs/db/observability/alert-thresholds.md`
- `docs/db/on-call-playbook.md`
