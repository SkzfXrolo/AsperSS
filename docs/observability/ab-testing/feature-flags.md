# Feature Flags (Deep)

## Comparativa plataformas

| Plataforma | Modelo | Fortalezas | Trade-offs |
|---|---|---|---|
| LaunchDarkly | SaaS | Madurez enterprise, targeting avanzado, analytics | Costo alto a escala |
| Unleash | OSS/self-host | Control total, costo predecible | Operacion propia |
| Flagsmith | OSS + SaaS | Flexible deployment, buen SDK coverage | Menor ecosistema enterprise |
| DevCycle | SaaS | DX fuerte, progressive delivery simple | Menor presencia que LD |
| PostHog Flags | SaaS/self-host | Integrado con producto/analytics | Feature depth menor en flags puros |

## Criterios de eleccion Argus

- Compliance y residencia de datos.
- Coste por MAU/evaluaciones.
- Necesidad de kill switch global en <1 minuto.
- Integracion con experimentacion y observabilidad.

## Recomendacion de arquitectura

- Flags de alto riesgo: reglas centralizadas + auditoria obligatoria.
- TTL para flags temporales.
- Metricas: evaluaciones/segundo, latencia SDK, errores de evaluacion, stale config.
