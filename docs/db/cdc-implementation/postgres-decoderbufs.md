# pgoutput y decoderbufs (Pack 48-H Round 5 · #135)

## pgoutput (nativo)

Desde PostgreSQL 10, el módulo **`pgoutput`** es el **logical decoding output plugin** por defecto para publicaciones nativas (`CREATE PUBLICATION` / `CREATE SUBSCRIPTION`).

- Integrado en el core; no requiere extensiones extra.
- Usado por replicación lógica integrada y por conectores que consumen el protocolo lógico.

## decoderbufs (protobuf)

**`decoderbufs`** es un plugin común en ecosistemas Debezium históricos; serializa cambios a **Protocol Buffers** para consumo por herramientas externas.

- Puede requerir **compilación/instalación** en el servidor (no siempre disponible en managed DB).
- En **Render/managed**: asumir **no disponible** salvo confirmación explícita.

## Elección para Argus

| Contexto | Recomendación |
| --- | --- |
| Logical rep PG → PG | `pgoutput` implícito |
| Debezium en PG managed con sólo plugins core | Preferir **`pgoutput`** |
| Necesidad protobuf custom en self-host | Evaluar `decoderbufs` vs `wal2json` |

## wal2json (nota)

Plugin popular para JSON; útil en scripts; mismas limitaciones managed que `decoderbufs`.

## Parámetros relacionados

```sql
SHOW wal_level;           -- logical
SHOW max_wal_senders;
SHOW max_replication_slots;
```

## Mensajes y formatos

- `pgoutput` emite según protocolo replication; no es JSON humano por defecto.
- Para inspección humana: logical decoding slot + `pg_recvlogical` (avanzado) o usar Debezium con serialización a JSON en Kafka.

## Referencias

- PostgreSQL docs: Logical Decoding Output Plugins
- `docs/db/cdc-implementation/debezium.md`
