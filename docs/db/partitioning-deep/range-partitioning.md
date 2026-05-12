# RANGE partitioning (Pack 48-H Round 6 · #152)

## Concepto

Cada partición almacena rows cuyo **valor de partition key cae en un rango** `[from, to)`. Tipo dominante para **series temporales**.

## Sintaxis

```sql
CREATE TABLE scans (
  id BIGSERIAL,
  company_id INTEGER NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  payload JSONB
) PARTITION BY RANGE (created_at);

CREATE TABLE scans_2026_05 PARTITION OF scans
  FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
```

## Ventajas

- **Partition pruning**: planner descarta particiones por predicate.
- **DROP partition** instantáneo vs `DELETE` masivo.
- **Constraint exclusion** moderno por defecto.

## Pitfalls

- PK debe incluir partition key: `PRIMARY KEY (id, created_at)`.
- FKs **a** tabla particionada: PG13+.
- FKs **desde** tabla particionada hacia otras: OK.
- `ON CONFLICT` requiere índice/constraint en partition key.

## Argus

- `scans` mensual.
- `ai_decisions_log` semanal.
- `staff_audit_log` trimestral.

Ver `argus-partitioning-candidates.md`.

## Referencias

- `docs/db/partitioning-design.md` (Round 3)
- `docs/db/partitioning-deep/partition-pruning.md`
