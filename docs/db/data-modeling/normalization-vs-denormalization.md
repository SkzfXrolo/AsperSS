# Normalization vs denormalization (Pack 48-H Round 6 · #157)

## Normalización (3NF)

- Cada hecho una sola vez.
- FKs explícitas.
- Updates seguros.

## Denormalización

- Datos duplicados intencionalmente para evitar JOIN.
- Útil en read-heavy + latency crítico.

## Patrones híbridos Argus

- Core OLTP: 3NF.
- Read paths panel: MV o columnas denormalizadas con triggers para `last_*`.

## Reglas

- Denormalizar **después** de medir.
- Siempre fuente de verdad clara; campos denormalizados marcados (`-- denorm`).

## Referencias

- `docs/db/materialized-views.md`
- `docs/db/data-modeling/audit-log-patterns.md`
