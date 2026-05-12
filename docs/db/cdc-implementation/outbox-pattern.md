# Outbox pattern (Pack 48-H Round 5 · #135)

## Problema

Tras un `COMMIT` en PostgreSQL, disparar side-effects (HTTP, Kafka) desde el mismo request puede causar:

- **Doble envío** si el commit OK pero el side-effect falla y se reintenta.
- **Orden inconsistente** vs otros replicas/consumidores.

## Patrón outbox

En la **misma transacción** que muta datos de negocio, insertar una fila en `outbox` con el evento serializado.

```text
BEGIN;
  UPDATE scans SET ...;
  INSERT INTO outbox_events (aggregate_type, aggregate_id, payload, created_at)
  VALUES ('scan', :id, :json, NOW());
COMMIT;
```

Un proceso **relay** (polling o `LISTEN/NOTIFY` + worker) lee `outbox_events` y publica a Kafka/Pulsar/HTTP, luego marca como enviado o borra.

## Tabla outbox mínima

| Columna | Tipo | Notas |
| --- | --- | --- |
| `id` | BIGSERIAL PK | Orden total |
| `aggregate_type` | TEXT | ej. `scan`, `ban` |
| `aggregate_id` | TEXT/UUID | Id estable |
| `payload` | JSONB | Evento |
| `created_at` | TIMESTAMPTZ | |
| `published_at` | TIMESTAMPTZ NULL | NULL = pendiente |

Índices:

```sql
CREATE INDEX idx_outbox_pending ON outbox_events (id) WHERE published_at IS NULL;
```

## Relay: polling vs NOTIFY

| Método | Pros | Contras |
| --- | --- | --- |
| Polling cada N ms | Simple, robusto | Latencia mínima = N |
| `NOTIFY` | Baja latencia | No garantía entrega si worker caído |
| Híbrido | NOTIFY + periodic sweep | Recomendado |

## Relación con CDC

- **Outbox**: control fino, payload explícito, no expone internals de tablas.
- **CDC**: captura todo cambio; útil para analytics; más acoplado al schema físico.

Argus puede combinar: **outbox** para eventos de producto; **CDC** para réplica DW.

## Retención

- Tras `published_at` seteado, archivar o borrar en batch (cuidado legal si payload tiene PII).

## Referencias

- `docs/db/cdc-implementation/use-cases-argus.md`
- `scripts/db/functions/triggers.sql` (NOTIFY patterns Round 4)
