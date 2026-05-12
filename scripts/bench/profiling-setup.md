# Profiling Toolchain Setup (Pack48-G)

## py-spy

- Local:
  - `py-spy top -- python web_app/app.py`
- Staging/prod:
  - `py-spy record -o flame.svg --pid <PID> --duration 60`

## Pyroscope

- Instalar agente Python.
- Configurar `server_address`, `app_name`, `tenant tags`.

## Artifacts

- Guardar flamegraphs en artifacts de CI/staging.
- Nombrar por commit SHA y timestamp.

## Diff de perfiles

- Comparar baseline vs current para detectar regresiones.
- Priorizar stacks que crecen en tiempo total y samples.
