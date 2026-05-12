# Event streaming: Kafka y Pulsar (Pack 48-H Round 5 · #135)

## Rol del stream en CDC DB → sistema

La base de datos **no** debería ser el bus de eventos de largo plazo. El patrón sano:

1. Capturar cambios (logical decoding / Debezium / outbox).
2. Publicar a **log append-only** (Kafka/Pulsar).
3. Consumidores idempotentes con **keys** estables (`company_id:entity_id`).

## Kafka

| Concepto | Uso |
| --- | --- |
| Topic | Por entidad o por aggregate (ej. `argus.scans` vs `argus.domain.events`) |
| Partition key | `company_id` para orden por tenant |
| Compaction | Sólo si modelo clave-valor y retention adecuado |
| Schema Registry | Avro/Protobuf + evolución de schema |
| Consumer groups | DW, cache, audit trail |

**Ordering**: garantías sólo **por partición**. Si orden importa por `scan_id`, particionar por hash de `scan_id` o por `company_id` si negocio lo permite.

## Pulsar

- Tenancy nativo (`tenant/namespace/topic`).
- Geo-replication opcional.
- Bueno si ya estándar en la org; curva de ops distinta a Kafka.

## Patrones de integración

| Patrón | Descripción |
| --- | --- |
| CDC directo | Debezium → Kafka |
| Outbox relay | App escribe `outbox` table → poller → Kafka |
| Hybrid | Outbox para writes críticos; CDC para tablas append-only históricas |

## Latencia y RPO

- RPO evento ≈ lag CDC + lag producer Kafka + batching.
- Objetivo Argus panel near-real-time: **< 5–30 s** según carga.

## Errores y reintentos

- Dead letter topic (`*.DLQ`) con payload + error.
- Idempotencia en consumer: `UPSERT` por natural key o tabla `processed_events(event_id PK)`.

## Referencias

- `docs/db/cdc-implementation/outbox-pattern.md`
- `docs/db/cdc-design.md` (Round 3)
