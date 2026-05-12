# Profiling Production Traffic (Pack48-G)

## Herramientas

- py-spy (bajo overhead)
- Pyroscope
- Datadog Continuous Profiler

## Modelo operativo

- Always-on con sampling bajo (1-5%) en servicios críticos.
- On-demand para incidentes específicos.

## Buenas prácticas

- limitar overhead de profiler.
- anonimizar datos sensibles.
- capturar CPU + alloc profiles.

## Acción desde flamegraphs

1. identificar top stacks.
2. mapear a endpoint/feature.
3. priorizar fixes por impacto total.
