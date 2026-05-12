# Profiling Runbook (Pack48-G)

## Herramientas

- `py-spy` (sampling sin modificar código)
- `cProfile` (profile determinístico)
- `line-profiler` (hotspots por línea)
- `memory-profiler` (uso de memoria por función)

## Flujo recomendado

1. Reproducir caso lento con dataset realista.
2. Correr `py-spy` para identificar funciones top.
3. Profundizar con `cProfile` en ruta específica.
4. Si persiste duda, usar `line-profiler` en función crítica.
5. Validar memoria con `memory-profiler`.

## Comandos ejemplo

```bash
py-spy top -- python web_app/app.py
python -m cProfile -o profile.out scripts/bench/bench_ml_training.py
python -m memory_profiler source/main.py
```

## Criterio de salida

- Top 3 funciones costosas identificadas.
- Acción concreta por función (cache, index, algoritmo, batching).
- Re-medición post-fix con mismo escenario.
