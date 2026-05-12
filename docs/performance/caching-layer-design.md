# Caching Layer Design (Pack48-G)

## Objetivo

Definir patrones de cache Redis para endpoints y cálculos costosos.

## Patrones recomendados

### Cache-aside (default)
- App consulta cache.
- Miss -> consulta DB, guarda en cache con TTL.
- Ideal para reads frecuentes.

### Write-through (casos puntuales)
- En write, persistir DB y cache de forma coordinada.
- Útil en estructuras críticas donde se requiere coherencia más fuerte.

## Claves sugeridas

- `stats:global:v1`
- `stats:company:{id}:v1`
- `ai:weights:company:{id}`
- `scans:list:{filters_hash}:page:{n}`

## TTL sugeridos

- Stats dashboard: 15-60s
- Pesos AI: 60-300s
- Listas de scans: 10-30s

## Invalidación

- Por evento (nuevo scan, nuevo feedback, cambio de pesos).
- Por versión de schema (`:v2` en key prefix).

## Riesgos y mitigación

- Stampede en expiración simultánea -> jitter TTL.
- Datos stale excesivos -> TTL cortos + invalidación por evento.
