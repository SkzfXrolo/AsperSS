# Index strategies deep (Pack 48-H Round 5 · #141)

## Selección

| Necesidad | Índice |
| --- | --- |
| Equality + range time | B-tree compuesto `(tenant, created_at DESC)` |
| JSON contenido | GIN jsonb_path_ops |
| Texto fuzzy | GIN `pg_trgm` |
| Series temporales append-only | BRIN sobre `created_at` |
| Unique soft | partial unique index `WHERE deleted_at IS NULL` |

## Partial indexes

```sql
CREATE INDEX idx_open ON scans(company_id) WHERE status = 'open';
```

## INCLUDE (covering)

```sql
CREATE INDEX idx_cov ON scans(company_id) INCLUDE (risk_score, created_at);
```

## Write amplification

Cada índice extra penaliza INSERT/UPDATE. Medir `idx_scan` vs coste.

## Reindex strategy

- `REINDEX CONCURRENTLY` en ventana.
- Evitar duplicados prefix (`anti-patterns.md`).

## Referencias

- `scripts/db/additional-indexes.sql`
- `docs/db/performance/buffer-cache-tuning.md`
