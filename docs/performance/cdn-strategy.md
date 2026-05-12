# CDN Strategy (Pack48-G)

## Objetivo

Reducir latencia global y descarga en origen usando edge caching.

## Propuesta

- CDN principal: Cloudflare (o Bunny como alternativa costo-eficiente).
- Cachear agresivamente `static/*` versionado (`?v=` o hash en filename).
- Mantener bypass para endpoints dinámicos y autenticados.

## Reglas recomendadas

1. `Cache-Control: public, max-age=31536000, immutable` para JS/CSS/img versionados.
2. `stale-while-revalidate` para assets secundarios.
3. Brotli habilitado en edge.
4. HTTP/3 habilitado.
5. WAF + rate limiting para proteger origen.

## Riesgos

- Cache poisoning si no se separa bien contenido autenticado.
- Invalidez de cache si se reutilizan filenames sin versionado.

## Métricas de éxito

- TTFB global -20% a -40%.
- Egress desde origen -30% a -70%.
