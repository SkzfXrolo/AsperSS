# Cost of Observability (Pack48-G)

## Resumen

Observabilidad completa mejora MTTR y confiabilidad, pero tiene costo operativo.

## Capas y costo relativo

1. **Logs estructurados**: costo bajo-medio, valor alto.
2. **Métricas**: costo bajo, valor muy alto para alerting.
3. **Tracing distribuido**: costo medio-alto, valor alto en debugging complejo.
4. **Retención larga**: costo alto, usar políticas por severidad.

## Estrategia costo/beneficio

- Empezar con métricas + logs (80/20).
- Habilitar tracing con sampling (5-15%).
- Subir sampling temporalmente durante incidentes.

## Control de costos

- Redactar logs verbose en prod.
- Sampling adaptativo por endpoint/error.
- Retención escalonada:
  - debug: 3-7 días
  - info: 14-30 días
  - error/audit: 90+ días
