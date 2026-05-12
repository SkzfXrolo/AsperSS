# Partial indexes (Pack 48-H Round 6 · #155)

## Definición

Índice con `WHERE` que cubre **subset** de filas. Menor tamaño + mantenimiento.

```sql
CREATE INDEX idx_scans_open
  ON scans (company_id, created_at DESC)
  WHERE status = 'open';
```

## Cuándo

- Predicate frecuente y selectivo.
- Subset estable (no cambia categorías constantemente).

## Argus

- `WHERE deleted_at IS NULL` para soft-delete tablas.
- `WHERE risk_score >= 75` para queries de alerta.

## Pitfalls

- Query debe contener el predicate del WHERE para usar el índice.

## Referencias

- `scripts/db/additional-indexes.sql`
