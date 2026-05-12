# Temporal data patterns (Pack 48-H Round 6 · #157)

## Tipos de "historia"

| Tipo | Descripción |
| --- | --- |
| Append-only log | una fila por evento; `created_at` |
| SCD Type 2 | versiones con `valid_from`, `valid_to` |
| Bi-temporal | tiempo de validez + tiempo de transacción |
| Effective dating | `effective_at` |

## SCD Type 2 ejemplo

```sql
CREATE TABLE prices (
  id BIGSERIAL PK,
  product_id INT,
  price NUMERIC,
  valid_from TIMESTAMPTZ NOT NULL,
  valid_to TIMESTAMPTZ
);
CREATE INDEX ... USING gist (product_id, tstzrange(valid_from, valid_to));
```

## Argus

- `companies.tier_history` candidato SCD2 si tiers cambian frecuentemente.
- `ai_decisions_log` ya es log append-only.

## Referencias

- `docs/db/data-modeling/versioned-rows.md`
