# Pack48-G Render Tuning Recommendations

## Estado actual observado

- Deploy en Render con gunicorn y **2 workers**.
- La app inicia threads daemon de background (`init_db_async`, ML loop, daily brief).
- Caches en memoria de proceso (`_stats_cache`, `_AI_WEIGHTS_CACHE`, `_ML_MODEL_CACHE`), no compartidas entre workers.

## Recomendaciones prioritarias

### 1) Worker model: separar web de jobs

- **Problema:** con 2 workers, cada worker puede arrancar loops ML/brief y duplicar trabajo.
- **Recomendación:**
  - Mantener web en gunicorn sin jobs embebidos, o
  - permitir jobs solo en un proceso líder con lock DB.
- **ROI:** alto; evita retrains duplicados y reduce carga innecesaria.

### 2) Worker count tuning

- Si plan Render es limitado en CPU/RAM, 2 workers pueden pelearse por CPU en picos de queries pesadas.
- **Sugerencia inicial:**
  - `workers = 2` si hay >1 vCPU real y tráfico concurrente.
  - `workers = 1` si CPU pequeña y p95 sube por contention (validar con métricas).
- **Regla práctica:** priorizar p95 estable antes que throughput bruto.

### 3) DB connection pooling

- Usar pool explícito (o pgbouncer externo) para evitar churn de conexiones.
- Config sugerida:
  - `pool_size` conservador por worker.
  - `max_overflow` pequeño.
  - `pool_pre_ping=True`.
  - `pool_recycle` menor que timeout de infra.
- **ROI:** medio-alto en estabilidad y latencia bajo carga.

### 4) Cache strategy: Redis sí vale la pena

- Caches actuales son in-process, por lo que con múltiples workers hay misses cruzados.
- Redis recomendado para:
  - stats dashboard,
  - pesos AI (`ai_weights`),
  - respuestas frecuentes de `/api/scans` con filtros comunes.
- **ROI:** alto para bajar query pressure y homogenizar latencia entre workers.

### 5) Timeouts y límites operativos

- Definir timeout de request y de DB claros para evitar worker stalls.
- Limitar endpoints pesados con límites estrictos (`limit <= 50/100` según endpoint).
- Agregar circuit breaker simple para jobs ML en caso de backlog.

## Configuración sugerida (base)

- gunicorn:
  - `workers`: 1-2 según vCPU (medir).
  - `threads`: 2-4 para I/O bound ligero.
  - `timeout`: 60 (ajustar con tracing real).
- DB:
  - pooling activo.
  - índices de `index-recommendations.sql` aplicados por fases.
- Cache:
  - Redis con TTL por endpoint (10s, 30s, 60s, 300s según volatilidad).

## Plan de rollout recomendado

1. Aplicar índices críticos (fase 1).
2. Habilitar lock de jobs para evitar duplicados (fase 1).
3. Introducir Redis para 2-3 endpoints más calientes (fase 2).
4. Re-test p95 y ajustar workers 1 vs 2 con datos reales (fase 2).
