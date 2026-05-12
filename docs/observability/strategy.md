# Observability Strategy (Pack48-G)

## Objetivo

Tener visibilidad end-to-end de:
- backend web,
- scanner,
- plugin,
- frontend.

## Pilares

1. **Logs estructurados JSON** con correlación.
2. **Metrics** de negocio + sistema (p50/p95/p99, errores, throughput).
3. **Tracing distribuido** por request y por operación crítica.

## Principios

- Todo evento relevante con `request_id` / `trace_id`.
- Alertar por SLO burn-rate, no solo por CPU.
- Dashboards por servicio y por journey (login, scans, oracle eval).
- Retención por nivel (debug corto, error largo).

## Fases

- Fase 1: logs JSON + métricas HTTP + errores.
- Fase 2: tracing distribuido + dashboards SLO.
- Fase 3: auto-remediation y capacity forecasting.
