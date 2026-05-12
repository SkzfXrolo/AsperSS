# Cloudflare Workers (Deep)

## Casos concretos para Argus

- Rate limiting por IP + API key antes de llegar al origen.
- Validacion preliminar de tokens firmados.
- Cache de endpoints publicos de reputacion con TTL corto.
- Reescritura de imagenes/thumbnails para panel web.

## Snippet: rate limit simple

```javascript
export default {
  async fetch(req, env) {
    const key = req.headers.get("cf-connecting-ip") || "unknown";
    const used = await env.RL.get(key);
    const count = Number(used || "0");
    if (count > 120) return new Response("Too Many Requests", { status: 429 });
    await env.RL.put(key, String(count + 1), { expirationTtl: 60 });
    return fetch(req);
  }
}
```

## Snippet: cache perimetral

```javascript
const cache = caches.default;
const cacheKey = new Request(new URL(req.url), req);
let res = await cache.match(cacheKey);
if (!res) {
  res = await fetch(req);
  res = new Response(res.body, res);
  res.headers.set("Cache-Control", "public, max-age=30");
  ctx.waitUntil(cache.put(cacheKey, res.clone()));
}
return res;
```

## Riesgos

- Estado distribuido limitado.
- Debug cross-region.
- Control de costo por requests y egress.
