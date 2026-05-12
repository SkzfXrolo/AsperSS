# CDN Advanced Strategy (Pack48-G)

## Edge functions (Cloudflare Workers)

Use cases:

1. Cache de respuestas API read-only con `stale-while-revalidate`.
2. Rate limiting en edge por IP/tenant.
3. Geo-routing a regiones óptimas.

## Image CDN

Opciones:
- Cloudflare Images
- ImageKit
- Imgix

Beneficio: resize/format dinámico (WebP/AVIF) según cliente.

## Invalidación

- Tag-based (por recurso lógico).
- Time-based (TTL).
- Version-based (hash de build).

## Recomendación

- Híbrido: version-based para estáticos + tag-based para respuestas cacheadas de API.
