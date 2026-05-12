# Cumplimiento XDG para Argus Scanner (Linux)

Este documento define como **deberia** manejar rutas el scanner Python en Linux para cumplir con la especificacion XDG Base Directory.

> Alcance: documentacion y validacion. La implementacion en `source/` se coordina con otro subagente.

## Rutas recomendadas

- Configuracion persistente: `$XDG_CONFIG_HOME/argus-scanner/config.json`
- Cache temporal: `$XDG_CACHE_HOME/argus-scanner/`
- Estado local y DB liviana: `$XDG_STATE_HOME/argus-scanner/`
- Logs rotativos: `$XDG_STATE_HOME/argus-scanner/logs/`

Si una variable XDG no existe:

- `XDG_CONFIG_HOME` -> `~/.config`
- `XDG_CACHE_HOME` -> `~/.cache`
- `XDG_STATE_HOME` -> `~/.local/state`

## Que evitar

- Escribir por defecto en el directorio del proyecto.
- Crear archivos en `~/` sin subdirectorio.
- Hardcodear rutas tipo `/home/<user>/...`.

## Checklist operativo

1. Resolver rutas XDG al iniciar la app.
2. Crear directorios con permisos de usuario (`0700` o equivalentes).
3. Mantener separacion config/cache/state.
4. Permitir override por variables de entorno.
5. Documentar migracion de rutas legacy.

## Script de apoyo

Usar `scripts/linux/check-xdg.sh` para validar que el entorno Linux exporta variables XDG validas antes de ejecutar pruebas de integracion.
