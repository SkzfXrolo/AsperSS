# APM Deep (Pack48-G)

## Propagación de contexto

- Estandarizar `traceparent` y `request_id` en todos los hops.

## Span attributes

- `service.name`, `endpoint`, `tenant_id`, `status_code`, `latency_ms`, `error.type`.

## Error tracking

- Stack traces, breadcrumbs, user context anonimizado.

## Performance budgets por endpoint

- Definir p95/p99 y payload budget para rutas críticas.

## Vendor comparison

- Datadog APM: operativo rápido.
- New Relic: fuerte en full-stack.
- Dynatrace: muy completo, costo alto.
- OTel self-hosted: flexible, más operación propia.
