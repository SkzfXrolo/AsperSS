# Backpressure & Rate Limiting (Pack48-G)

## Algoritmos

- Token bucket
- Leaky bucket
- Sliding window

## Niveles de límite

- por usuario
- por tenant
- por endpoint

## Estrategia

- límites más estrictos para operaciones costosas (oracle eval, reportes pesados).
- límites más flexibles para lecturas livianas autenticadas.

## Degradación elegante

- responder `429` + `Retry-After`.
- cola diferida para tareas no críticas.
