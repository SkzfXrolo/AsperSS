# Secrets Management (Argus)

## Reglas base

- nunca commitear secretos en git.
- usar variables de entorno o secret manager.
- rotar claves regularmente.
- separar secretos por entorno (dev/staging/prod).
- restringir acceso por mínimo privilegio.

## Qué NO hacer

- hardcodear `SECRET_KEY`, passwords admin, tokens API.
- imprimir secretos en logs o errores.
- reusar misma key para múltiples servicios.

## Rotación recomendada

- plugin keys: 30-90 días
- session/app secret: 90 días o tras incidente
- webhooks/API keys externas: 30-90 días

## Respuesta ante fuga

1. revocar credencial comprometida,
2. emitir nueva credencial,
3. invalidar sesiones relacionadas,
4. revisar logs de uso anómalo.
