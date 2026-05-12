# Runbook deployment

## Render
1. Validar variables.
2. Deploy de nueva version.
3. Verificar healthchecks y logs.

## Self-hosted
1. Build/pull imagenes.
2. `docker compose up -d`.
3. Verificar DB migrations y endpoints.
