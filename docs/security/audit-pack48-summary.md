# Pack48-F Security Audit Summary (web_app)

Fecha: 2026-05-12  
Scope auditado: `web_app/app.py`, `web_app/auth.py`, `web_app/templates/*`, `web_app/static/js/*`, `web_app/requirements.txt`, `minecraft_plugin/argus-mc/pom.xml`.

## Top 5 issues críticos

1. **[NEW][CRITICAL] Endpoint de bootstrap admin expone credenciales y crea cuenta por GET**  
   Evidencia: `web_app/app.py` (`/setup-admin-aspers2024`).  
   Impacto: toma total de la aplicación si se invoca antes/durante estados de setup.

2. **[NEW][CRITICAL] Credenciales SuperAdmin hardcodeadas por fallback**  
   Evidencia: `web_app/app.py` (fallback `SUPER_ADMIN_USER='Rodrigo'`, `SUPER_ADMIN_PASS='Rodrigo@1'`).  
   Impacto: acceso no autorizado al panel super admin si env vars faltan/mal configuradas.

3. **[NEW][HIGH] Secreto interno hardcodeado para endpoint interno de revisión**  
   Evidencia: `web_app/app.py` (`_REVIEW_SECRET = 'aspers-claude-review-2026'`).  
   Impacto: acceso a datos sensibles de scans con token conocido o filtrado.

4. **[NEW][HIGH] Endpoints de diagnóstico/debug públicos con metadata sensible**  
   Evidencia: `web_app/app.py` (`/api/db-stats`, `/api/db-status`, `/api/debug/last-scan`).  
   Impacto: facilita reconocimiento de infraestructura, tablas y superficie de ataque.

5. **[NEW][HIGH] CSRF y controles anti-abuso incompletos en endpoints de sesión y login**  
   Evidencia: no hay `CSRFProtect`, cookie `SameSite=Lax`, login sin rate-limit robusto global.  
   Impacto: operaciones de sesión y acciones con cookie quedan más expuestas en escenarios de navegador.

## Hallazgos cuantitativos (rápido)

- Hallazgos activos priorizados: **16** (2 Critical, 8 High, 5 Medium, 1 Low).
- Hallazgos marcados como ya mitigados o defensas parciales: **7** (`[FIXED]`/parcial).
- Falsos positivos descartados: **5** (`[FALSE POSITIVE]`), principalmente SQLi por uso correcto de placeholders `_PH`.

## Estado de production readiness

**No recomendado para producción endurecida sin hardening previo.**  
Bloquear primero:

1. eliminar/fijar bootstrap admin + fallbacks hardcodeados,
2. mover secretos hardcodeados a variables rotables,
3. cerrar endpoints debug/health sensibles detrás de auth/red privada,
4. introducir CSRF real + política de cookies más estricta,
5. aplicar rate-limiting consistente a login, auth y APIs costosas (AI/scanner).
