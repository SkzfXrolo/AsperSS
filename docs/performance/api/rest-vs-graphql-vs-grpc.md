# REST vs GraphQL vs gRPC (Deep)

## Tabla comparativa (30 dimensiones)

| Dimension | REST | GraphQL | gRPC |
|---|---|---|---|
| 1. Estilo | Recurso/endpoint | Grafo tipado | RPC tipado |
| 2. Transporte principal | HTTP/1.1-3 | HTTP/1.1-2 | HTTP/2 |
| 3. Payload default | JSON | JSON | Protobuf |
| 4. Tamaño payload | Medio/alto | Medio (controlable) | Bajo |
| 5. Latencia p50 | Buena | Buena | Muy buena |
| 6. Latencia p99 | Variable | Puede degradar en resolvers | Estable |
| 7. Streaming | SSE/WebSocket aparte | Subscriptions | Nativo bidi |
| 8. Cache CDN | Excelente | Limitado por POST | Limitado |
| 9. Cache app | Simple por URL | Requiere normalizacion | Por metodo/clave |
| 10. Evolucion esquema | Versionado explicito | Depracaciones suaves | Versionado de proto |
| 11. Contract-first | Opcional (OpenAPI) | Si (schema) | Si (proto) |
| 12. Tooling cliente | Amplio | Muy amplio | Bueno en backend |
| 13. Debug humano | Muy facil | Medio | Menor (binario) |
| 14. Observabilidad | Estandar | Compleja por resolvers | Muy buena por interceptor |
| 15. Seguridad | Madura (WAF/API GW) | Compleja por query depth | Fuerte mTLS/interceptors |
| 16. Control de cuotas | Endpoint-based | Query-cost-based | Method-based |
| 17. N+1 risk | Bajo | Alto si no hay DataLoader | Bajo/medio |
| 18. Over-fetching | Alto | Bajo | Bajo |
| 19. Under-fetching | Medio | Bajo | Bajo |
| 20. Browser soporte | Nativo | Nativo | Requiere gRPC-Web |
| 21. Mobile eficiencia | Media | Media | Alta |
| 22. Gateway complejidad | Baja | Media/alta | Media |
| 23. Curva de aprendizaje | Baja | Media | Media |
| 24. Error model | HTTP status | Error envelope | Status codes gRPC |
| 25. Retries idempotentes | Sencillos | Segun operacion | Muy bien soportados |
| 26. Compatibilidad legacy | Excelente | Buena | Menor |
| 27. Multi-tenant governance | Simple | Requiere policy por campo | Muy buena por metadata |
| 28. Coste de red | Medio | Medio | Bajo |
| 29. Coste operativo | Bajo/medio | Medio/alto | Medio |
| 30. Fit Argus actual | Alto | Medio-alto | Alto interno |

## Decision tree rapido

- Si el consumidor principal es **web publica + CDN**: usar REST.
- Si necesitas **composicion flexible de UI** y equipos frontend fuertes: GraphQL.
- Si priorizas **latencia, contratos fuertes y backend-to-backend**: gRPC.
- Si hay mezcla de canales: REST externo + gRPC interno + GraphQL solo para BFF.

## Ejemplos Argus

- **REST (recomendado):** panel admin, endpoints de reporte, APIs publicas con cache.
- **GraphQL (selectivo):** vistas analiticas del dashboard con joins de multiples dominios.
- **gRPC (recomendado interno):** comunicacion web_app <-> servicios de scoring/ML de baja latencia.
