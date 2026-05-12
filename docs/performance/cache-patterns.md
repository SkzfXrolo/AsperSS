# Cache Invalidation Patterns (Pack48-G)

## Estrategias

- Cache-aside
- Write-through
- Write-back
- Refresh-ahead

## Triggers de invalidación

1. TTL
2. Evento (CDC/webhook)
3. Acción explícita admin

## Multi-level cache

- L1: in-process
- L2: Redis
- L3: CDN

## Diseño de keys

- Namespace por tenant/entorno.
- Versionado de schema (`v1`, `v2`).
- Evitar colisiones con prefijos claros.
