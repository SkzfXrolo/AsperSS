# Index additions plan (Pack 49) (Pack 48-H Round 5 · #149)

## Fuente

`scripts/db/additional-indexes.sql` (Round 1) + `query-performance.md` (Round 2).

## Priorización

| Prioridad | Índice ejemplo | Justificación |
| --- | --- | --- |
| P0 | `(company_id, created_at DESC)` en `scans` | panel timeline |
| P0 | `ai_decisions_log(company_id, timestamp DESC)` | incident queries |
| P1 | partial indexes en estados abiertos | ratio selectividad |
| P2 | BRIN `created_at` append-only | storage |

## Procedimiento prod

1. Ventana off-peak.
2. `CREATE INDEX CONCURRENTLY` (migration Alembic `transactional_ddl=false`).
3. `ANALYZE` tabla post-index.
4. Medir `pg_stat_user_indexes` tras 7d; rollback drop si `idx_scan=0`.

## Métricas éxito

- p95 queries top 10 ↓ ≥15%.
- No aumento significativo `blk_write_time` inserts.

## Referencias

- `docs/db/migration-runbook.md`
