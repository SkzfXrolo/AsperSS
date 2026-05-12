# 50 Performance Anti-Patterns

1. Consultas N+1.
2. `SELECT *` en endpoints críticos.
3. Falta de índices compuestos.
4. Cache sin invalidación definida.
5. Reintentos sin backoff.
6. Polling agresivo en frontend.
7. Carga síncrona de scripts de terceros.
8. Imágenes sin compresión.
9. Bundle JS monolítico.
10. Logging excesivo en hot path.
11. Serialización JSON innecesaria repetida.
12. Bloqueos globales en memoria compartida.
13. Threads sin límites.
14. Procesos CPU-bound en request thread.
15. Falta de timeouts.
16. Falta de circuit breaker.
17. Fan-out sin control.
18. Falta de colas para picos.
19. Falta de backpressure.
20. GC pressure por objetos temporales masivos.
21. Queries sin paginación.
22. Paginación offset en tablas gigantes.
23. JOINs no selectivos.
24. Índices no usados por mala cardinalidad.
25. Triggers pesados en escritura frecuente.
26. Transacciones largas.
27. Lock escalation evitable.
28. Falta de particionamiento.
29. Replicas sin estrategia de lag.
30. API sin batching.
31. API versioning roto.
32. WebSocket sin límites por cliente.
33. TLS handshake repetitivo sin keep-alive.
34. DNS lookups excesivos.
35. Falta de CDN en activos estáticos.
36. Cache-control incorrecto.
37. SSR sin streaming para páginas pesadas.
38. CSR puro en páginas SEO críticas.
39. Estados frontend gigantes no normalizados.
40. Sync frecuente en mobile sin delta.
41. Sin modo offline-first donde aplica.
42. Entrenamiento ML sin early stopping.
43. Inferencia ML sin batch adaptativo.
44. Sin observabilidad de token cost en LLM.
45. Sin trazas distribuidas en rutas críticas.
46. Alertas ruidosas sin severidad.
47. SLOs sin error budget policy.
48. Cambios sin prueba de carga.
49. Deploy sin canary/rollback automático.
50. Optimizar sin perfilado previo.
