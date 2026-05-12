# Bench Plugin Simulado (JMH) — Pack48-G

## Objetivo

Definir microbenchmarks reproducibles para paths críticos del plugin Java:
- `ViolationManager.flag()/addViolation` equivalente
- `PacketDataStore.pushMove()`

## Targets

- `ViolationManager.addViolation()` < **10 µs** p95
- `PacketDataStore.pushMove()` < **5 µs** p95

## Setup sugerido con JMH

1. Agregar módulo benchmark (ej. `minecraft_plugin/argus-mc-bench`).
2. Dependencias:
   - `org.openjdk.jmh:jmh-core`
   - `org.openjdk.jmh:jmh-generator-annprocess`
3. Ejecutar benchmarks con JVM fija (Java 17), sin profiler externo inicialmente.

## Ejemplo conceptual de benchmark

```java
@BenchmarkMode(Mode.SampleTime)
@OutputTimeUnit(TimeUnit.MICROSECONDS)
@State(Scope.Thread)
public class PacketDataStoreBench {
    private PacketDataStore.State s;

    @Setup
    public void setup() { s = new PacketDataStore.State(); }

    @Benchmark
    public void benchPushMove() {
        s.pushMove(System.currentTimeMillis());
    }
}
```

## Parámetros recomendados

- Warmup: `5 x 1s`
- Measurement: `10 x 1s`
- Forks: `2`
- Threads: `1, 2, 4, 8` (para stress lock contention)

## Qué interpretar

- Si `pushMove` escala mal con threads >2, revisar `synchronized`.
- Si `ViolationManager` supera target, revisar:
  - loops sobre colas,
  - logging síncrono,
  - llamadas colaterales en ruta crítica.

## Entregable esperado por corrida

- CSV/JSON con p50/p95/p99 por benchmark.
- Delta vs baseline anterior (regresión si >15%).
