# Cryptographic Review — Pack48 Round 2

Scope principal: `web_app/app.py`, `web_app/auth.py`, plugin API client, scanner/mobile clients.

## 1) Password hashing

- **Actual:** `PBKDF2-SHA256` con 260k iteraciones + salt aleatorio (`auth.py`).
- **Fortaleza:** uso de `secrets.compare_digest`.
- **Riesgo [MEDIUM]:** compatibilidad legacy con SHA256 sin sal permanece activa.
- **Recomendación:** migración transparente a Argon2id/bcrypt moderno y eliminación del fallback legacy.

## 2) Token generation

- **Actual:** se observan tokens con `secrets.token_urlsafe()` en múltiples flujos.
- **Estado:** correcto para entropía.
- **Riesgo residual:** exposición de token en logs/config local.

## 3) API keys

- **Plugin keys:** prefijo `argus_pk_` + longitud alta (secrets token-based).
- **Riesgo [HIGH]:** replay protection incompleta (sin nonce/timestamp firmado end-to-end).
- **Recomendación:** HMAC request signing + expiración temporal.

## 4) Session cookies

- `HttpOnly=True`, `Secure=True` en prod, `SameSite=Lax`.
- **Riesgo [MEDIUM]:** Lax no cubre todos los escenarios de CSRF para acciones sensibles.
- **Recomendación:** `SameSite=Strict` para panel admin + CSRF token real.

## 5) JWT

- No se evidenció uso central de JWT en las rutas auditadas de `web_app`.
- **Nota:** si se introduce JWT multi-tenant, preferir `RS256/EdDSA`, expiración corta y rotación de claves.

## 6) Secrets management

- **Hallazgo [HIGH]:** presencia histórica/actual de secretos y credenciales fallback hardcodeadas en app.
- **Recomendación:** fail-closed cuando faltan secretos críticos, vault/env manager, rotación inmediata.

## 7) Transporte seguro

- Clientes usan TLS estándar, pero sin pinning extendido.
- **Riesgo [MEDIUM]:** trust-store compromise scenarios.
- **Recomendación:** pinning opcional en plugin/scanner/android para tenants sensibles.

## Prioridades criptográficas

1. eliminar credenciales/secrets hardcodeados y rotar,
2. deprecar hash legacy SHA256 sin sal,
3. anti-replay criptográfico para API plugin/clientes,
4. CSRF + endurecer cookies de sesión,
5. pinning opcional en clientes.
