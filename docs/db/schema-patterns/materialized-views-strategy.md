# Materialized views strategy (Pack 48-H Round 6 · #162)

## Decisión

Para Argus, MVs **simples** sobre agregaciones panel + refresh CONCURRENTLY periódico.

## Naming

`mv_<grano>_<dominio>_<resumen>`: `mv_daily_scan_stats`, `mv_oracle_confidence_distribution`.

## Refresh

- 5 min sliding (panel near-real-time).
- 1 hora batch (estadísticas).

## Concurrency

- Requiere UNIQUE index sobre claves del MV.

## Roadmap

1. Pack 49: deploy MVs base.
2. Pack 50: cron externo refresh (pg_cron pendiente Render).
3. Pack 52: evaluar incremental updates manuales si MV cae a >5s refresh.

## Referencias

- `docs/db/postgres-topics/materialized-views-deep.md`
