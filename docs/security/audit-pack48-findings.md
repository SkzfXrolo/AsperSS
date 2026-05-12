# Pack48-F Detailed Findings (web_app)

Convenciones: `[NEW]` hallazgo activo, `[FIXED]` mitigado en el estado actual, `[FALSE POSITIVE]` no aplica tras revisión.

## 1) SQL Injection

- `[FALSE POSITIVE][LOW]` Uso extendido de f-strings con `_PH` en queries.
  - Evidencia: múltiples ocurrencias en `web_app/app.py` y `web_app/auth.py`.
  - Análisis: el patrón usa placeholder de driver (`%s`/`?`) y parámetros separados.
  - Recomendación: mantener `_PH` pero evitar interpolación cuando no sea imprescindible.

- `[NEW][MEDIUM]` SQL dinámico por nombre de tabla (aunque desde allowlist local).
  - Evidencia: `web_app/app.py` (`cur.execute(f'SELECT COUNT(*) FROM {t}')`).
  - Riesgo: hoy `t` viene de lista hardcodeada, pero es deuda técnica para futuras regresiones.
  - Patch sugerido:
    ```python
    SAFE_TABLES = {"scans","scan_results", ...}
    if t not in SAFE_TABLES:
        raise ValueError("invalid table")
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    ```

## 2) XSS

- `[NEW][HIGH]` DOM XSS por `innerHTML` con campos no escapados de backend.
  - Evidencia: `web_app/static/js/panel.js` (render de `e.reason` y `e.changed_by` en historial).
  - Riesgo: si un texto almacenado en DB contiene HTML/JS, puede ejecutarse en sesión staff.
  - Recomendación: `escapeHtml()` en TODOS los campos interpolados o usar `textContent`.

- `[NEW][MEDIUM]` Inserción directa de respuesta IA en HTML.
  - Evidencia: `web_app/static/js/panel.js` (`el.innerHTML = ... + text` en resumen IA).
  - Riesgo: proveedor IA o prompt injection podría inyectar payload HTML.
  - Recomendación: renderizar texto plano (`textContent`) o sanitizar strict.

- `[FIXED][LOW]` Existe helper `escapeHtml()` y se usa en muchas rutas UI.
  - Evidencia: `web_app/static/js/panel.js` función `escapeHtml`.
  - Estado: mitigación parcial, pero no uniforme.

## 3) CSRF

- `[NEW][HIGH]` No se observa protección CSRF server-side (`flask_wtf`/token).
  - Evidencia: sin `CSRFProtect`, sin verificación de token en POST/PUT/DELETE.
  - Riesgo: acciones autenticadas pueden ser forzadas desde navegador víctima.
  - Recomendación: token CSRF sincronizado + validación `Origin/Referer` en endpoints sensibles.

- `[NEW][MEDIUM]` `SESSION_COOKIE_SAMESITE='Lax'` (no Strict).
  - Evidencia: `web_app/app.py`.
  - Riesgo: reduce pero no elimina vectores CSRF (top-level nav/GET).
  - Recomendación: `Strict` para paneles admin o separación de cookies por contexto.

- `[NEW][MEDIUM]` Endpoints de cambio de estado vía GET.
  - Evidencia: `/logout`, `/setup-admin-aspers2024`, algunos debug GET.
  - Riesgo: activación involuntaria por navegación/clickjacking.
  - Recomendación: mutaciones solo POST + CSRF.

## 4) AuthN/AuthZ

- `[NEW][CRITICAL]` Bootstrap admin inseguro.
  - Evidencia: `web_app/app.py` (`/setup-admin-aspers2024`).
  - Problemas: método GET, credencial fija (`arefy2024!`), hash SHA-256 legacy.
  - Recomendación: eliminar endpoint en producción, migrar a runbook one-shot offline.

- `[NEW][CRITICAL]` Credenciales SuperAdmin por fallback hardcodeado.
  - Evidencia: `web_app/app.py` (`SUPER_ADMIN_USER/PASS` fallback).
  - Recomendación: fail-closed si faltan env vars + rotación inmediata.

- `[FIXED][LOW]` Logout limpia sesión y borra cookie.
  - Evidencia: `_build_logout_response()` usa `session.clear()` + `delete_cookie`.
  - Estado: mejora respecto al issue histórico; revisar invalidación adicional si hay token server-side.

- `[NEW][MEDIUM]` Enumeración de usuarios.
  - Evidencia: `authenticate_user()` diferencia `Usuario no encontrado` vs `Contraseña incorrecta` en `web_app/auth.py`; endpoint `/api/admin/check-user` devuelve metadata de usuario.
  - Recomendación: mensajes uniformes y restringir `/api/admin/check-user` con auth fuerte o eliminar.

## 5) Information Disclosure

- `[NEW][HIGH]` Endpoints públicos de debug/db.
  - Evidencia: `/api/db-stats`, `/api/db-status`, `/api/debug/last-scan`.
  - Riesgo: exposición de estructura DB, columnas, volumen y contenido reciente.

- `[NEW][HIGH]` Secreto hardcodeado para endpoint interno.
  - Evidencia: `web_app/app.py` `_REVIEW_SECRET` + `/internal/scan-review/<id>?token=...`.
  - Riesgo: acceso no autorizado a detalle de scans.

- `[NEW][MEDIUM]` `debug=True` en arranque directo.
  - Evidencia: `app.run(..., debug=True)`.
  - Riesgo: exposición de stack traces y behavior inseguro en ejecuciones no-Gunicorn.

## 6) Rate Limiting

- `[NEW][HIGH]` Login sin rate limit dedicado.
  - Evidencia: `/api/auth/login` no usa throttling; limitador global solo cubre rutas no usadas (`/api/submit`, etc.).
  - Riesgo: brute force/password spraying.

- `[NEW][MEDIUM]` Endpoints AI costosos con límite parcial o ausente.
  - Evidencia: `/api/ai/assistant/ask` tiene límite en sesión, pero otros endpoints IA/ML no comparten política robusta por IP/user/company.
  - Recomendación: cuota por actor + burst + costo por endpoint.

- `[FIXED][LOW]` Plugin keys sí tienen cuota diaria.
  - Evidencia: `company_plugin_keys.daily_quota/used_today` en `/api/plugin/issue-token`.

## 7) File Upload / Payloads

- `[NEW][MEDIUM]` `start_scan` acepta payload JSON grande sin `MAX_CONTENT_LENGTH`.
  - Evidencia: `web_app/app.py` `/api/scans` y campos extensos.
  - Riesgo: DoS por memoria/CPU y costos DB.
  - Recomendación: límite de tamaño de body + validación estricta de esquema.

- `[FALSE POSITIVE][LOW]` Path traversal clásico en `/download/<filename>`.
  - Evidencia: path se compone con lista fija de bases + `os.path.isfile`.
  - Estado: no se observó explotación directa obvia; reforzar `secure_filename` igualmente.

## 8) Crypto / Secrets

- `[NEW][HIGH]` `SECRET_KEY` por defecto débil/hardcodeado.
  - Evidencia: `app.secret_key = os.environ.get('SECRET_KEY', 'aspers-secret-key-change-in-production')`.
  - Riesgo: si se despliega sin env, sesión/cookies firmadas predecibles.

- `[FIXED][LOW]` Comparación segura en passwords PBKDF2.
  - Evidencia: `secrets.compare_digest` en `verify_password`.

- `[NEW][MEDIUM]` Compatibilidad legacy SHA-256 sin sal aún activa.
  - Evidencia: fallback en `verify_password`.
  - Recomendación: migración on-login a PBKDF2/Argon2id y deprecación del fallback.

## 9) Dependencies

- `[NEW][MEDIUM]` Dependencias pinneadas viejas o rango abierto sin lock reproducible.
  - Evidencia: `web_app/requirements.txt` (`flask==3.0.0`, `requests==2.31.0`, múltiples `>=`).
  - Riesgo: drift de supply chain y falta de SBOM/lock.
  - Recomendación: `pip-tools/uv lock`, revisión CVE periódica, Dependabot.

- `[NEW][LOW]` `pom.xml` usa snapshots/provided sin pipeline explícito de escaneo CVE.
  - Recomendación: OWASP dependency-check en CI.

## 10) Privacy

- `[NEW][MEDIUM]` Logging de datos potencialmente sensibles en claro.
  - Evidencia: logs con username, IP, machine_name, errores detallados.
  - Riesgo: exposición en agregadores de logs/soporte.
  - Recomendación: redacción de IP/token/identificadores + niveles de log por entorno.

- `[NEW][LOW]` Sin política explícita de retención en código para `scan_results`, `ai_decisions_log`, `ai_feedback`.
  - Recomendación: TTL por tabla + purga programada + base legal (LGPD/GDPR).

## 11) Argus-specific

- `[NEW][HIGH]` Flujo plugin depende de `argus_pk_*` en header; sin pinning/canal mutuo.
  - Evidencia: `/api/plugin/issue-token` y `/api/plugin/violation`.
  - Riesgo: robo/replay de key fuera de TLS/entorno comprometido.
  - Recomendación: rotación corta de keys, firma HMAC por request, nonce + timestamp.

- `[FIXED][LOW]` Buen aislamiento multi-tenant en plugin violations.
  - Evidencia: filtros por `company_id` y checks de rol en endpoints listados.
  - Estado: no se vio bypass obvio en rutas auditadas.

---

## REVIEW / hipótesis que requieren validación adicional

- `REVIEW:` confirmar en entorno Render que endpoints debug estén realmente expuestos públicamente y no bloqueados por red/WAF.
- `REVIEW:` validar si existen claves históricas comprometidas de `SUPER_ADMIN_*` y `_REVIEW_SECRET` (rotación forzada recomendada).
- `REVIEW:` evaluar impacto real de XSS con datos de `verdict_reason` existentes en base de producción.
