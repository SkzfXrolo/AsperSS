# CDC use cases específicos Argus (Pack 48-H Round 5 · #135)

## Objetivos de negocio

| Caso | Fuente | Consumidor | Latencia target |
| --- | --- | --- | --- |
| Invalidar cache panel | `scans`, `violations` | Redis / app workers | < 10 s |
| DW incremental | `scans`, `ai_decisions_log` | DuckDB/BigQuery | 1–15 min |
| Auditoría staff | `staff_audit_log` | SIEM / S3 archive | minutos |
| Oracle retraining dataset | `ai_decisions_log`, feedback | ML pipeline | horas |
| Búsqueda jugador | `ai_player_profiles` | OpenSearch (futuro) | minutos |

## Tablas candidatas (alta señal)

- `scans` — alto volumen; CDC por `id` + `created_at` partition-friendly.
- `ai_decisions_log` — append-only; ideal para streaming.
- `ban_history` — bajo volumen pero crítico; outbox + notificación legal.
- `staff_audit_log` — compliance; preferir outbox o CDC con masking.

## PII y masking

Antes de publicar a Kafka:

- Hashear IPs (`argus_anonymize_ip` en `scripts/db/functions/utility-functions.sql`).
- No enviar `password_hash` ni tokens; lista deny en connector/SMT.

## Orden y claves

- Partición Kafka por `company_id` para aislar backpressure por tenant grande.
- Key = `scan:{id}` o `decision:{uuid}` para compactación futura si aplica.

## Fallback sin infraestructura Kafka

1. `LISTEN/NOTIFY` en tablas críticas (baja escala).
2. Cron `SELECT ... WHERE updated_at > :watermark` (simple, más lag).

## Métricas

- Lag slot PG (`pg_replication_slots`).
- Consumer lag Kafka.
- Ratio `outbox pending` / `published`.

## Anti-patterns Argus

- CDC de **toda** la DB hacia topic único → imposible evolucionar schemas.
- Exponer WAL a terceros sin TLS mútuo.

## Referencias

- `docs/db/dw-export-design.md`
- `docs/db/cdc-design.md`
- `docs/db/data-classification.md`
