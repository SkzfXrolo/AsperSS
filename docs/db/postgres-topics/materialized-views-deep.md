# Materialized views deep (Pack 48-H Round 5 · #140)

## vs MV Round 3

`materialized-views.md` define **qué** MV crear; este doc profundiza **cómo** operarlas.

## Refresh modes

| Modo | Lock | Uso |
| --- | --- | --- |
| `REFRESH MATERIALIZED VIEW` | bloquea lecturas brevemente (sin CONCURRENTLY) | dev |
| `REFRESH MATERIALIZED VIEW CONCURRENTLY` | permite lecturas; requiere **UNIQUE index** en MV | prod |

## Costos

- Refresh completo rescanea query base → CPU/IO.
- MV ancha sobre `scans` millonarios: considerar incremental manual (tabla resumen + triggers/outbox).

## Partitioned MV

No nativo como tablas; workaround: MV por partición lógica + `UNION ALL` view.

## Monitoring

```sql
SELECT relname, last_refresh FROM pg_stat_progress_create_materialized_view; -- según versión
```

## Argus

- `mv_daily_scan_stats` cada 5 min CONCURRENTLY si pg_cron no disponible → **cron externo** (F-008).

## Referencias

- `docs/db/materialized-views.md`
- `scripts/db/materialized-views.sql`
