# Playbook: Slow Endpoint (Deep)

## Workflow paso a paso

1. Confirmar impacto: endpoint, p95/p99, error rate, ventanas horarias.
2. Abrir traza distribuida y separar tiempo en app/DB/cache/red.
3. Verificar saturacion (CPU, memoria, pool DB, threads).
4. Revisar queries dominantes con `EXPLAIN (ANALYZE, BUFFERS)`.
5. Validar cache hit ratio y stampede.
6. Aplicar mitigacion rapida (rate-limit, cache temporal, degradacion controlada).
7. Definir fix estructural y prueba de regresion.

## Ejemplo Argus

- Endpoint: `/api/v1/reports`
- Sintoma: p99 sube de 450ms a 2.8s en picos.
- Hallazgo: N+1 en enriquecimiento de metadata + miss de cache.
- Mitigacion inmediata: cache por tenant 60s + limite de pagina.
- Fix definitivo: query agregada + indice compuesto + precalculo asincrono.

## Datos minimos para postmortem

- Timeline de degradacion.
- Query/funcion hot path.
- Cambio de codigo/config asociado.
- Acciones, owner y fecha de verificacion.
