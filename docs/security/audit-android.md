# Audit Android Client — Pack48 Round 2

Scope: `mobile/argus_android/**` (Manifest, Gradle, core networking code, CI build workflow).

## Resultado rápido

- Buen baseline: `allowBackup=false`, `usesCleartextTraffic=false`, firma release en CI, permisos explícitos.
- Riesgos principales: permisos amplios (especialmente `QUERY_ALL_PACKAGES`/storage), ausencia de pinning y release con minify/obfuscation desactivados.

## 1) Permisos y sobreprivilegios

- **Hallazgo [NEW][HIGH]:** `QUERY_ALL_PACKAGES` + `MANAGE_EXTERNAL_STORAGE` elevan superficie de privacidad y cumplimiento.
- **Contexto:** funcional para anti-cheat, pero alto impacto regulatorio/review store.
- **Recomendación:** justificar DPIA, degradar a permisos más acotados cuando sea posible, mode split por entorno.

## 2) AndroidManifest exports

- `MainActivity` exportada (`true`) por launcher/deeplink (esperado).
- `ScanForegroundService` exportada `false` (correcto).
- **Riesgo residual [LOW]:** deeplink `argus://scan` puede ser vector de abuso UX si no valida payload.
- **Recomendación:** validación estricta de parámetros de deeplink.

## 3) Certificate pinning / transporte

- **Hallazgo [NEW][MEDIUM]:** cliente usa `HttpURLConnection` con TLS estándar pero sin pinning.
- **Mitigación actual:** cleartext deshabilitado.
- **Recomendación:** Network Security Config con pins (SPKI hash) para dominios productivos.

## 4) Obfuscation / hardening binario

- **Hallazgo [NEW][MEDIUM]:** `isMinifyEnabled=false` en release; R8/ProGuard deshabilitado por compatibilidad.
- **Impacto:** ingeniería inversa más fácil, mayor exposición de lógica anti-cheat.
- **Recomendación:** reintroducir obfuscación progresiva con reglas de exclusión probadas.

## 5) `debuggable` en release

- No se observó flag release `debuggable=true`.
- **Estado:** sin hallazgo crítico en este punto.

## 6) Storage de secretos

- **Hallazgo [NEW][MEDIUM]:** no se observó uso de `EncryptedSharedPreferences` para token/config; diseño parece in-memory + parámetros runtime.
- **Riesgo:** si se persiste token en storage no cifrado en otras capas, exposición local.
- **Recomendación:** estandarizar secret storage con `EncryptedSharedPreferences` o Android Keystore.

## 7) Firma y distribución

- CI firma APK de release y verifica firma (fortaleza).
- **Riesgo residual [LOW/MEDIUM]:** falta de proceso público formal de verificación de hash para usuarios finales.
- **Recomendación:** publicar checksum SHA256 y guide de verificación.

## Prioridad Android

1. Pinning TLS.
2. Reintroducir obfuscación release.
3. Políticas de minimización/justificación para permisos altos.
4. Secret storage cifrado estándar.
