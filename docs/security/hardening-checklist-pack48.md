# Hardening Checklist Pack48 (Argus)

Formato: `[] Item — Esfuerzo (S/M/L) — Impacto (Low/Med/High/Critical)`

1. [] Eliminar endpoint `/setup-admin-aspers2024` en producción — S — Critical
2. [] Remover fallbacks hardcodeados `SUPER_ADMIN_*` — S — Critical
3. [] Mover `_REVIEW_SECRET` a env rotable y rotarlo — S — High
4. [] Deshabilitar `/api/debug/*` en producción — S — High
5. [] Proteger `/api/db-status` y `/api/db-stats` con auth admin — S — High
6. [] Forzar `SECRET_KEY` fuerte (fail-closed si falta) — S — Critical
7. [] Activar CSRF global (`CSRFProtect`) para endpoints sesión — M — High
8. [] Validar `Origin/Referer` en mutaciones sensibles — S — High
9. [] Revisar `SESSION_COOKIE_SAMESITE=Strict` en panel admin — S — Medium
10. [] Añadir `SESSION_COOKIE_SECURE=True` en todos los entornos no local — S — High
11. [] Implementar rate-limit por IP+user en login — M — High
12. [] Añadir bloqueo progresivo tras intentos fallidos — M — High
13. [] Uniformar errores de login para evitar enumeración — S — Medium
14. [] Restringir/eliminar `/api/admin/check-user` — S — High
15. [] Rate-limit por costo para endpoints AI/ML — M — High
16. [] Límite de tamaño (`MAX_CONTENT_LENGTH`) para `/api/scans` — S — High
17. [] Validar esquema JSON estricto en scanner/plugin payloads — M — High
18. [] En plugin API, exigir timestamp + nonce anti-replay — M — High
19. [] Firmar requests plugin con HMAC por key rotable — M — High
20. [] Rotación automática y revocación rápida de `argus_pk_*` — M — High
21. [] Auditoría de acceso para superadmin y endpoints internos — M — High
22. [] Sanitizar TODO render con `innerHTML` en `panel.js` — M — High
23. [] Reemplazar `innerHTML` por DOM APIs/textContent donde posible — M — High
24. [] Sanitizar salida de IA antes de renderizar en UI — S — High
25. [] Agregar CSP estricta (`default-src 'self'`) — M — High
26. [] Agregar headers de seguridad (HSTS, X-Frame-Options, XCTO) — S — Medium
27. [] Revisar CORS (orígenes explícitos, no wildcard en prod) — S — High
28. [] Agregar política de retención por tabla (scans/ai logs/feedback) — M — Medium
29. [] Redactar tokens, IP y PII en logs — M — High
30. [] Clasificar datos personales (UUID/IP/username) por sensibilidad — M — Medium
31. [] Crear runbook de incident response para fuga de key/token — M — High
32. [] Agregar migración on-login de hashes SHA256 legacy a PBKDF2/Argon2id — M — High
33. [] Deprecar fallback SHA256 sin sal tras ventana de migración — M — High
34. [] Instrumentar alertas de anomalías auth (brute force, spray) — M — High
35. [] Instrumentar alertas para picos en `/api/scans` y AI endpoints — M — High
36. [] Crear suite de tests de seguridad en CI (auth, CSRF, rate) — M — High
37. [] Integrar escaneo SAST en PRs (Bandit/Semgrep) — S — Medium
38. [] Integrar SCA/dependencias (Dependabot + pip-audit + osv-scanner) — S — Medium
39. [] Generar lockfile reproducible para Python deps — M — Medium
40. [] Agregar escaneo CVE Maven (`dependency-check`) para plugin — S — Medium
41. [] Definir política de rotación de secretos trimestral — S — High
42. [] Revisar exposición de variables env en panel SA, incluso masked — S — Medium
43. [] Endurecer endpoint interno `/internal/scan-review/*` (auth real) — M — High
44. [] Añadir feature flag para endpoints operativos/diagnóstico — M — Medium
45. [] Implementar revisión de permisos por compañía en endpoints nuevos — M — High
46. [] Crear checklist de release secure-by-default para Render — S — High
47. [] Documentar matriz de activos in-scope/out-of-scope pública — S — Medium
48. [] Planificar pentest externo anual del stack Argus — L — Medium
