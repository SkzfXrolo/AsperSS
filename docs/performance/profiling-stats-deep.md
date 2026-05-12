# Profiling Stats Deep (Pack48-G)

## Arquitectura de profiling continuo

- Opción self-hosted: Pyroscope o Parca.
- Agentes en web/scanner/workers con sampling controlado.

## Análisis avanzado

- Flamegraphs CPU: funciones más costosas por endpoint.
- Memory profiles: crecimiento por request/job.
- Lock contention: secciones críticas y waits.

## Differential profiling

- Comparar baseline vs PR/release.
- Reportar delta en top stacks (tiempo total y samples).

## Sampling

- Time-based (periódico): simple.
- Event-based (errores/p95 alto): eficiente para señales críticas.
