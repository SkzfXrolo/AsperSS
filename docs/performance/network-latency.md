# Network Latency Optimization (Pack48-G)

## HTTP/2 vs HTTP/3

- HTTP/2: maduro, multiplexing, buen soporte.
- HTTP/3 (QUIC): menor head-of-line blocking en redes inestables.

## TLS

- Usar TLS 1.3 por defecto.
- Evaluar 0-RTT solo para requests idempotentes (riesgo replay).

## Conexiones

- Keep-alive activo.
- Reutilización de conexiones en backend y plugin.

## Compresión

- Brotli para estáticos.
- gzip fallback.
- zstd evaluar en canales internos/edge compatible.

## Resource hints

- `preconnect`, `dns-prefetch`, `preload` para recursos críticos.
- Evitar abuso de preload (puede competir con recursos esenciales).
