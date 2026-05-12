# Event-Driven Architecture (Deep)

## Patrones recomendados

- Eventos inmutables con versionado explicito.
- Outbox pattern para consistencia entre DB y broker.
- Consumer idempotente por `event_id`.
- Dead-letter queues + retry con backoff exponencial.

## Anti-patrones comunes

- Publicar eventos sin contrato estable.
- Reintentos infinitos sin DLQ.
- Side effects no idempotentes.
- Eventos demasiado gordos o con datos sensibles.

## Blueprint Argus

- Dominio deteccion: `scan.completed`, `violation.detected`, `score.updated`.
- Dominio operacion: `alert.created`, `rule.changed`.
- SLO de pipeline: latencia evento->accion < 5s p95.

## Observabilidad minima

- Lag por consumer group.
- Tasa de retries y DLQ.
- Tiempo end-to-end por evento.
- Fallos por tipo de handler.
