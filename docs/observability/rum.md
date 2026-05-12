# Real User Monitoring (RUM) (Pack48-G)

## Objetivo

Medir experiencia real de usuarios (LCP, CLS, INP/FID) en producción.

## Implementación base

- Librería `web-vitals` en frontend.
- Envío a endpoint `POST /api/rum/vitals`.

Payload sugerido:

```json
{
  "metric": "LCP",
  "value": 2120,
  "path": "/panel",
  "user_agent": "...",
  "ts": 1715500000
}
```

## Tools comparison

- Sentry RUM: buena integración errores + perf.
- Datadog RUM: robusto enterprise.
- Cloudflare Analytics: simple y edge-friendly.
- Plausible: enfoque privacy-first.

## Sampling strategy

- Base 5-10% de sesiones.
- Subir a 20-30% en ventanas de investigación.
- Filtrar bots y tráfico interno.

## Dashboard spec

- LCP p50/p75/p95 por ruta.
- INP p75 por ruta/dispositivo.
- CLS distribución.
- Error rate correlacionado con vitals.
