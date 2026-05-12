# Observability Cost Reduction (Pack48-G)

## Log volume

- JSON estructurado y campos estables.
- Sampling en INFO/DEBUG.
- DEBUG solo opt-in temporal.

## Cardinalidad de métricas

- Máximo recomendado: <10 labels por métrica.
- Evitar labels de alta cardinalidad (`user_id`, `scan_id`).

## Traces

- Tail-based sampling priorizando errores y p99 alto.
- Head sampling bajo para tráfico normal.

## Retención por tier

- Hot: 7 días
- Warm: 30 días
- Cold: 365 días

## Vendor cost comparison (alto nivel)

- Datadog: rápido de operar, costo alto.
- Splunk: potente, costo alto en ingest.
- ELK self-hosted: menor licencia, mayor costo operativo/infra.
