# CSRF Exempt List (web_app)

Este documento enumera las rutas exentas de CSRF en `web_app/app.py` y la razón.

## Endpoints exentos explícitos

- `POST /api/auth/login`
  - Login inicial sin cookie de sesión previa.
- `POST /api/auth/register`
  - Registro inicial sin sesión autenticada.
- `POST /api/validate-token`
  - Consumido por scanner desktop sin navegador/sesión.
- `POST /setup-admin-aspers2024`
  - Bootstrap one-shot protegido por token de entorno.
- `POST /api/scans`
  - Inicio de scan desde cliente scanner.
- `POST /api/scans/<scan_id>/results`
  - Upload de resultados desde cliente scanner.
- `POST /api/plugin/issue-token`
  - Plugin Minecraft (auth por API key).
- `POST /api/plugin/violation`
  - Plugin Minecraft (auth por API key).
- `POST /api/plugin/ai-evaluate`
  - Plugin Minecraft (auth por API key).
- `POST /api/plugin/assistant/query`
  - Plugin Minecraft (auth por API key).

## Notas operativas

- Todas las rutas de panel staff/superadmin con sesión web mantienen CSRF activo.
- Si se agrega una ruta machine-to-machine nueva, debe evaluarse explícitamente si requiere exención.
