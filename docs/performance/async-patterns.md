# Async Work Patterns (Pack48-G)

## Cuándo usar async

- CPU pesado
- I/O lento
- tareas largas no críticas para request-response

## Opciones

- Celery
- RQ
- Dramatiq
- asyncio stdlib

## Comparación rápida

- Celery: potente, más compleja.
- RQ: simple, menos features avanzadas.
- Dramatiq: buen balance simplicidad/performance.
- asyncio: útil intra-proceso, no reemplaza cola distribuida.

## Recomendación Argus

- Dramatiq + Redis para:
  - batch oracle eval,
  - post-procesado scans,
  - sincronización plugin.
