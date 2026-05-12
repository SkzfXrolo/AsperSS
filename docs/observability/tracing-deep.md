# Distributed Tracing Deep

- Adoptar W3C Trace Context y `baggage`.
- Span attributes estándar: `http.method`, `http.route`, `db.statement`, `messaging.system`.
- Head vs tail sampling:
  - head: simple/barato,
  - tail: mejor para errores/latencia extrema.
- Propagación en async (Celery/asyncio) con contexto explícito.
- Correlación cross-service: web -> plugin -> backend -> DB.
