# DynamoDB → PostgreSQL (Pack 48-H Round 6 · #160)

## Modelado

- Tablas Dynamo single-table → re-modelar en relacional.
- PK (partition + sort) → PG PK compuesto.
- GSI → índices secundarios PG.

## Migración

- Stream Dynamo → Lambda → PG (CDC pattern).
- Snapshot completo con `aws dynamodb scan` (cuidado con throughput).

## Costos

Dynamo + GSI puede ser barato a baja escala; PG ahorra a escala alta.

## Argus

No aplica directamente; referencia para evaluar alternativas en cache externo.

## Referencias

- `docs/db/cdc-implementation/event-streaming.md`
