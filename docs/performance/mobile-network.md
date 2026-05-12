# Mobile Networking Optimization (Pack48-G)

## Reducir request count

- Batching de operaciones.
- Consolidar endpoints cuando sea razonable.
- Evaluar GraphQL para agregación selectiva.

## Reducir payload

- JSON comprimido (gzip/brotli).
- Evaluar protobuf/MessagePack para flujos de alto volumen.

## Background sync

- WorkManager para sincronización diferida.
- Evitar foreground services salvo casos críticos.

## Network awareness

- Modo offline.
- Low-data mode.
- Reintentos con backoff exponencial.
