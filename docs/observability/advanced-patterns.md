# Observability Advanced Patterns (Pack48-G)

## Sampling

- Head-based: simple, barato.
- Tail-based: captura mejor errores/latencia extrema, más complejo.

## Correlation IDs

- Propagar `request_id` y `trace_id` en todo hop.

## Logging levels

- DEBUG: investigación puntual.
- INFO: eventos de negocio importantes.
- WARN: degradaciones recuperables.
- ERROR: fallos con impacto.

## Metrics conventions

- Naming Prometheus: `namespace_subsystem_metric_unit`.
- Labels estables y cardinalidad controlada.

## Trace context

- Usar estándar W3C Trace Context.
- Capturar atributos clave de span (tenant, endpoint, status, latency).
