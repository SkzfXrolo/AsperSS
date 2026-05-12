# Mobile Performance Benchmarks (Pack48-G)

## Frame rate

- Target 60fps.
- Nunca caer por debajo de 30fps sostenido.

## Jank detection

- GPU rendering profile.
- Analizar frames largos y UI thread blocking.

## ANR prevention

- Evitar trabajo pesado en main thread.
- Timeouts y watchdogs para I/O.

## Memory leaks

- Especificar integración LeakCanary para builds QA.
- Monitorear actividades/fragments retenidos.
