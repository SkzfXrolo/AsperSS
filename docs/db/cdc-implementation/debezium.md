# Debezium + PostgreSQL (Pack 48-H Round 5 · #135)

## Qué es Debezium

Debezium es un **CDC** open-source que lee el WAL de PostgreSQL y publica eventos de cambio (create/update/delete) a **Kafka** (u otros sinks vía Kafka Connect).

## Cuándo usarlo en Argus

- Necesitás **múltiples consumidores** (search index, DW, cache invalidation) del mismo stream de cambios.
- Querés **replay** y retención en Kafka en lugar de depender sólo del slot PG.
- Tenés capacidad de operar **Kafka Connect** (o servicio managed equivalente).

## Arquitectura mínima

```
PostgreSQL (WAL) → Debezium PG Connector → Kafka topics
                                              ↓
                                    consumers (dbt, ES, app)
```

## Connector PostgreSQL (conceptos)

- **Plugin**: `pgoutput` (nativo PG10+) preferido sobre `decoderbufs` cuando sea posible.
- **Publication**: Debezium puede crear una publicación propia o usar existente.
- **Slot**: nombre estable; **crítico monitorear lag** del slot vs retención Kafka.
- **Snapshot inicial**: modo `initial` hace dump consistente + luego streaming.

## Configuración típica (referencia)

Propiedades frecuentes (nombres exactos según versión Debezium):

| Propiedad | Rol |
| --- | --- |
| `database.hostname` | Host PG |
| `database.sslmode` | `require` / `verify-full` |
| `slot.name` | Identificador único por connector |
| `publication.name` | Nombre publicación |
| `table.include.list` | `public.scans,public.violations,...` |
| `heartbeat.interval.ms` | Heartbeat para avanzar LSN y evitar WAL bloat |
| `topic.prefix` | Prefijo topics Kafka |

## Seguridad

- Usuario dedicado `REPLICATION` + `SELECT` mínimo.
- No usar superuser.
- Rotación de passwords via secret manager.
- PII: usar **SMT** (Single Message Transform) para enmascarar campos o enrutar a topic segregado.

## Operación

| Riesgo | Mitigación |
| --- | --- |
| Slot lag → disco PG lleno | Alertas + `heartbeat` + límites de retención WAL coordinados |
| Schema evolution | Debezium schema history topic + compatibilidad Avro/JSON |
| Truncate / DDL | Revisar soporte por versión; plan manual |

## Alternativa ligera

`LISTEN/NOTIFY` o polling por `updated_at` para cargas bajas (ver `cdc-design.md` Round 3).

## Referencias

- `docs/db/cdc-implementation/postgres-decoderbufs.md`
- `docs/db/cdc-implementation/event-streaming.md`
- `docs/db/cdc-implementation/use-cases-argus.md`
