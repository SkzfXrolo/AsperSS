# JWT Implementation Spec

- algoritmo permitido: `RS256` o `ES256`.
- rechazar `none` y algoritmos no permitidos.
- claims requeridos: `iss`, `sub`, `aud`, `exp`, `iat`, `jti`.
- validar `aud` y `iss` exactos.
- rotación de claves por `kid`.
- TTL corto (15-30 min) y refresh separado.
