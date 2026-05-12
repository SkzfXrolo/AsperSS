# Plugin Minecraft Performance Deep (Pack48-G)

## Targets

- `< 5 µs` por check (microbench local).
- `< 10 µs` para `addViolation/flag`.
- Impacto de TPS cercano a cero en carga normal.

## Metodología de benchmark

- JMH con warmup y medición multi-thread.
- Escenarios:
  - packet burst,
  - combate intenso,
  - alta concurrencia por jugador.

## TPS Impact Analysis

1. Ejecutar en servidor staging con profiler activo.
2. Correlacionar MSPT/TPS con rate de checks y violations.
3. Medir overhead del plugin apagado vs encendido.

## async-profiler runbook (resumen)

```bash
./profiler.sh -d 60 -e cpu -f flamegraph.svg <pid_java>
./profiler.sh -d 60 -e alloc -f alloc.svg <pid_java>
```

- Revisar stacks de:
  - `PacketAnticheatListener`
  - `ViolationManager`
  - serialización HTTP plugin->web.

## Recomendaciones

- Batching de eventos HTTP al backend.
- Reducir lock contention en estado por jugador.
- Muestreo de logs en rutas frecuentes.
