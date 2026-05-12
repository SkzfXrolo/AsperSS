# PostgreSQL Tuning Guide (Pack48-G)

## Objetivo

Ajustar PostgreSQL para latencia más estable en lectura/escritura mixta.

## Parámetros clave

- `shared_buffers`: 20-25% RAM del host DB.
- `effective_cache_size`: 50-75% RAM (estimación de cache OS + DB).
- `work_mem`: empezar en 4-16MB, ajustar por concurrencia real.
- `maintenance_work_mem`: mayor en ventanas de VACUUM/INDEX.
- `max_connections`: limitar + usar pooler.

## Recomendaciones operativas

1. Usar pool de conexiones (evitar conexión por request).
2. Activar `pg_stat_statements`.
3. Revisar top queries por total_time semanalmente.
4. VACUUM/ANALYZE programado.
5. Monitorear bloat de índices/tablas.

## Targets sugeridos

- p99 query crítica < 200ms.
- cache hit ratio > 99% (lectura caliente).
- lock wait p95 bajo y estable.
