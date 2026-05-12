# API v2 migration (draft)

- Base path nueva: `/api/v2/...`.
- Respuestas de error estandarizadas: `{ "error": { "code", "message" } }`.
- Primeros endpoints disponibles: `GET /api/v2/health`, `GET /api/v2/meta`.

## Compatibilidad

- v1 sigue activa.
- Migrar clientes gradualmente a v2.
