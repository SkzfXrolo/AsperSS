# Performance Testing in CI (Pack48-G)

## Objetivo

Detectar regresiones de performance en PR antes de merge.

## Política sugerida

- Comparar baseline `main` vs resultados PR.
- Fallar PR si `p95` empeora > 10% en benchmarks críticos.

## Herramientas

- `pytest-benchmark`
- scripts de bench sintéticos ya existentes

## Flujo

1. Ejecutar benchmarks en CI.
2. Publicar artefacto JSON.
3. Comparar con baseline versionado.
4. Comentar resultado en PR con semáforo.

## Nota de scope

- Este documento define la especificación; no crea workflows fuera de scope permitido.
