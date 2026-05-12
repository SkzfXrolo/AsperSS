# HASH partitioning (Pack 48-H Round 6 · #152)

## Concepto

Particiones por **hash modulo N** del partition key. Distribuye uniformemente sin orden temporal.

## Sintaxis

```sql
CREATE TABLE scans_h (
  id BIGSERIAL, company_id INTEGER NOT NULL, ...
) PARTITION BY HASH (company_id);

CREATE TABLE scans_h_0 PARTITION OF scans_h FOR VALUES WITH (MODULUS 8, REMAINDER 0);
CREATE TABLE scans_h_1 PARTITION OF scans_h FOR VALUES WITH (MODULUS 8, REMAINDER 1);
-- ... hasta REMAINDER 7
```

## Ventajas

- Balance carga entre particiones.
- Adecuado para alta cardinalidad (muchos tenants).

## Pitfalls

- **No** soporta pruning por rango temporal.
- Cambiar N requiere migración costosa.
- Mezclar HASH con RANGE → sub-partitioning (avanzado).

## Argus

- Hash por `company_id` sólo si llegamos a > 1000 tenants activos y queremos paralelizar I/O.
- Antes evaluar **shared/shared + RLS** y read replicas.

## Referencias

- `docs/db/sharding/horizontal-sharding.md`
