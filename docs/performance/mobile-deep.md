# Mobile Android Performance Deep (Pack48-G)

## Targets

- Cold start: `< 500ms P50`, `< 1s P95`
- Idle memory: `< 50MB`
- APK release: `< 5MB`

## Cómo medir cold start

```bash
adb shell am start -W com.argus.scanner/.MainActivity
```

Registrar `TotalTime`, `WaitTime`, `ThisTime` en múltiples corridas.

## Memory baseline

- Android Studio Profiler + `dumpsys meminfo`.
- Medir idle, navegación y scan activo.

## Battery impact

- Battery Historian:
  - wake locks,
  - network usage,
  - background jobs.

## APK size optimization

- Habilitar R8 + shrinkResources.
- Revisar recursos duplicados.
- Evitar dependencias no esenciales.

## Recomendaciones

1. Baseline Profiles.
2. App Startup library para inicialización controlada.
3. Lazy init de módulos no críticos.
4. WorkManager para tareas diferidas.
