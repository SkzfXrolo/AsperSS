# Pack48-G Round2: Audit Performance Scanner Desktop

## Alcance

- `source/main.py`
- Foco en I/O, subprocess, serialización JSON, paralelismo y memoria.

## Hallazgos nuevos

### 1) I/O intensivo por scan completo
- Se observan múltiples `os.walk(...)` sobre roots amplios (incluye drives completos).
- Hay muchas operaciones `os.listdir`, `open`, hashing y lectura de archivos.
- Conteo rápido de patrones I/O/subprocess/threading en archivo: **~196 coincidencias**.

**Impacto estimado:** muy alto en hosts con discos grandes.

### 2) Lectura completa de archivos en memoria
- Hay casos de `f.read()` para JAR/hash/fingerprint.
- En archivos grandes eleva pico de memoria y GC pressure.

**Impacto estimado:** alto.

### 3) Overhead de subprocess por scan
- Se detecta uso de `subprocess.run(...)` en chequeos auxiliares.
- Spawn repetido incrementa latencia total.

**Impacto estimado:** medio-alto según frecuencia por scan.

### 4) Paralelismo parcial e inconsistente
- Existen `threading.Thread` para ciertos flujos UI/network.
- El grueso del escaneo filesystem/registry sigue mayormente serial.

**Impacto estimado:** alto (under-utilization en máquinas multicore).

### 5) Serialización JSON con stdlib
- Uso predominante de `json` estándar (no `orjson`).
- Correcto para compatibilidad, pero no óptimo en throughput puro.

**Impacto estimado:** medio-bajo comparado con I/O, pero útil en reportes grandes.

## Registro y Windows ops

- Registry scans y múltiples sectores forenses se ejecutan de forma secuencial.
- Oportunidad clara de paralelizar por “sector” (amcache, prefetch, registry, jars, procesos).

## Targets operativos sugeridos

- **Tiempo total scan:** < 60s en host típico.
- **Peak memory:** < 200MB.

## Recomendaciones priorizadas

1. **Arquitectura incremental**: índice local de archivos (mtime+size+hash parcial).
2. **Hash por chunks** en lugar de `f.read()` completo.
3. **Paralelizar por sectores** con `ThreadPoolExecutor` y budget de workers.
4. **Pruning agresivo de paths** (allowlist de roots realmente útiles).
5. **Batch de subprocess calls** y cache de resultados por sesión.
6. **Separar modo deep scan vs quick scan** para UX.
7. **Instrumentar tiempos por sector** para encontrar outliers reales.
