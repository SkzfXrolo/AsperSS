# LIST partitioning (Pack 48-H Round 6 · #152)

## Concepto

Particiones por **valores discretos** del partition key. Útil para enumeraciones cerradas: `region`, `tier`, `tenant_group`.

## Sintaxis

```sql
CREATE TABLE companies_by_tier (
  id INTEGER, tier TEXT NOT NULL, name TEXT
) PARTITION BY LIST (tier);

CREATE TABLE companies_free  PARTITION OF companies_by_tier FOR VALUES IN ('free');
CREATE TABLE companies_pro   PARTITION OF companies_by_tier FOR VALUES IN ('pro');
CREATE TABLE companies_other PARTITION OF companies_by_tier DEFAULT;
```

## Ventajas

- Aislamiento físico por categoría (analytics, cleanup).
- Distintos índices por partición si patrón de uso difiere.

## Pitfalls

- Cambio de categoría → `UPDATE` mueve la fila entre particiones (PG11+).
- Valores fuera de lista van a partition `DEFAULT` o fallan.

## Argus

- Posible para `companies` agrupadas por tier si workload por tier diverge.
- **No** usar para `company_id` directo (cardinalidad alta → hash mejor).

## Referencias

- `docs/db/partitioning-deep/hash-partitioning.md`
