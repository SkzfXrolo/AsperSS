# Secure Coding Java (Plugin ArgusMC)

## Top 10 prácticas

1. validar permisos por subcomando (`hasPermission`) de forma explícita.
2. no confiar en datos de packet/client; validar rangos y estados.
3. separar lógica Netty thread vs main Bukkit thread.
4. usar estructuras thread-safe para estado compartido.
5. evitar logs con PII sensible completa (UUID/IP).
6. no hardcodear API keys ni secrets.
7. aplicar timeouts estrictos en HTTP.
8. validar certificados/pinning para canal crítico.
9. sanitizar strings antes de enviarlas a backend/log.
10. fail-safe: ante error de check, degradar sin crash global.

## Bukkit/PacketEvents gotchas

- no tocar APIs no-thread-safe desde listeners de red.
- evitar bucles pesados por packet sin budget.
- agregar protección contra flood y replay.
