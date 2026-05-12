# Security Code Review Checklist (50)

## Core

1. validación de input
2. output encoding
3. queries parametrizadas
4. no secretos hardcoded
5. manejo seguro de errores
6. logs sin PII/secrets
7. authn robusta
8. authz por recurso
9. rate limiting
10. CSRF en mutaciones
11. sesión segura
12. control de subida de archivos
13. path traversal checks
14. SSRF controls
15. headers de seguridad
16. criptografía moderna
17. rotación de claves
18. anti-replay en APIs
19. idempotencia en operaciones críticas
20. protección brute force
21. control de dependencias
22. pinning de acciones CI
23. mínimos privilegios
24. separación de secretos por entorno
25. no debug endpoints públicos
26. audit trail crítico
27. monitoreo de anomalías
28. rollback plan
29. race condition review
30. timeouts/retries seguros
31. limitación de payload size
32. sanitización de logs
33. validación de MIME real
34. validación de firmas webhooks
35. manejo de expiración de tokens
36. revocación de credenciales
37. protección contra IDOR
38. anti-clickjacking
39. CORS mínimo necesario
40. pruebas de seguridad automatizadas
41. cobertura de casos negativos
42. manejo de concurrencia
43. bloqueo de funciones peligrosas
44. control de deserialización
45. no uso de eval dinámico
46. documentación de riesgos
47. feature flags seguras
48. observabilidad de seguridad
49. runbook de incidentes
50. plan de hardening pendiente

## Addendum por lenguaje

- Python: evitar `eval`, `pickle` inseguro, `yaml.load` sin safe loader.
- Java: deserialización insegura, XXE, reflection riesgosa.
- JavaScript: `eval`, DOM XSS, `innerHTML` sin escape.
