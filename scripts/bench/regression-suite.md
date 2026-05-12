# Regression Suite de Performance — Pack48-G

## Objetivo

Detectar regresiones comparando benchmark actual vs baseline JSON.

## Flujo

1. Ejecutar suite completa (`run_all.sh`).
2. Guardar resultados actuales (`current.json`).
3. Comparar contra baseline (`baseline.json`).
4. Marcar regresión si delta supera umbral.

## Umbrales sugeridos

- Regresión severa: +20% latencia o -20% throughput.
- Regresión moderada: +10% en p95/p99 de endpoints críticos.

## Salida recomendada

- `report.md` con:
  - métricas por benchmark,
  - semáforo (OK/WARN/FAIL),
  - top 5 regresiones detectadas.
