# Wide vs tall tables (Pack 48-H Round 6 · #162)

## Wide (denormalizada)

- Muchas columnas, una fila por entidad.
- Lectura simple, escritura puntual.
- Costoso si muchas son NULL.

## Tall (EAV-like / time-series)

- Pocas columnas, muchas filas por entidad.
- Query agregado con GROUP BY.
- Más índices necesarios.

## Argus

- `scans`: wide razonable (campos comunes a todo scan).
- `scan_metrics` hipotético tall: si métricas son dinámicas, mejor JSONB.

## Decisión guía

> Si > 30% columnas NULL constantemente → considerar tall o JSONB.

## Referencias

- `docs/db/anti-patterns.md`
