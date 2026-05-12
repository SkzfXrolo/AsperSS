# Pack48-G Round2: Audit Performance Android

## Estado del módulo Android

Se detecta proyecto Android en:
- `mobile/argus_android/app/build.gradle.kts`

## Hallazgos

### 1) Minify/shrink desactivado en release
- `isMinifyEnabled = false`
- `isShrinkResources = false`

**Impacto:** APK más grande y mayor costo de cold start/class loading.

### 2) Stack relativamente liviano
- No se observan dependencias de red pesadas tipo Retrofit/OkHttp/Gson en gradle app.
- Base Compose + coroutines (razonable).

### 3) No evidencia de Baseline Profiles
- No se ven módulos/artefactos de baseline profiles.

**Impacto:** startup y navegación peor en dispositivos de gama media/baja.

## Métricas objetivo

- **Cold start:** < 1.8s (dispositivo medio)
- **APK size:** < 12MB ideal
- **Memoria baseline en idle:** < 120MB (ajustar por device)

## Recomendaciones priorizadas

1. Rehabilitar gradualmente R8 (`minify`) con reglas controladas.
2. Activar `shrinkResources` al estabilizar reglas Proguard.
3. Introducir Baseline Profiles para Compose startup paths.
4. Lazy init de componentes no críticos al arranque.
5. Medir startup con Macrobenchmark y perfetto traces.
6. Revisar assets e íconos redundantes para reducir APK.

## Gap vs target (estimado)

- Sin métricas instrumentadas en esta ronda; el principal gap probable está en tamaño de APK y startup por minify desactivado.
