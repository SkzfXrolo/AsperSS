# Benchmark Scanner Full (Pack48-G)

## Objetivo

Estandarizar cómo medir un scan completo de scanner desktop y desglosarlo por sector.

## Comando propuesto

```bash
python -m source.main --benchmark --output=bench.json
```

> Si el flag `--benchmark` aún no existe, usar wrapper temporal que mida tiempo por función `scan_*`.

## Métricas mínimas a capturar

- `total_scan_ms`
- `peak_memory_mb`
- `disk_reads_count` (estimado)
- `subprocess_spawn_count`
- tiempos por sector:
  - `scan_processes_ms`
  - `scan_minecraft_files_ms`
  - `scan_all_jars_ms`
  - `scan_recent_files_ms`
  - `scan_registry_complete_ms`
  - `scan_services_ms`
  - `scan_downloads_folder_ms`

## Tabla comparativa sugerida

| Sector | Baseline ms | Current ms | Delta % | Target ms |
|---|---:|---:|---:|---:|
| amcache/shimcache |  |  |  |  |
| registry |  |  |  |  |
| jars/filesystem |  |  |  |  |
| procesos |  |  |  |  |
| prefetch/jna |  |  |  |  |
| total |  |  |  | < 60000 |

## Criterio de regresión

- Regresión severa: +20% o más en `total_scan_ms`.
- Regresión moderada: +10% en un sector crítico (jars/filesystem/registry).
- Alerta memoria: `peak_memory_mb > 200`.

## Frecuencia

- Ejecutar en cada release del scanner.
- Guardar `bench.json` versionado para comparar sprint a sprint.
