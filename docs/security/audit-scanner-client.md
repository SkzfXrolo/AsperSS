# Audit Scanner Client (Windows/Linux) — Pack48 Round 2

Scope: `source/main.py`, `source/db_integration.py`, `source/argus_linux/scanner.py`, build/release workflows.

## Hallazgos clave

## 1) Validación de paths y output local

- **Observación:** hay utilidades de escritura atómica (`_atomic_write_json_locked`) y múltiples normalizaciones de paths.
- **Riesgo [NEW][MEDIUM]:** `config.json` y artefactos se buscan/guardan en rutas locales múltiples (incluyendo AppData) sin firma de integridad del archivo.
- **Impacto:** manipulación local de `api_url`/`scan_token` por malware o usuario local.
- **Recomendación:** proteger secretos con DPAPI/OS keyring y validar origen de config.

## 2) Validación de respuestas del server / MITM

- **Observación:** uso de `requests`/`urllib` con HTTPS; no se detectó `verify=False`.
- **Hallazgo [NEW][MEDIUM]:** no hay certificate pinning ni validación adicional de identidad backend.
- **Impacto:** riesgo residual frente a CA comprometida/proxy interceptante.
- **Recomendación:** pinning opcional (SPKI/public key hash) en entornos de alto riesgo.

## 3) Almacenamiento local de credenciales/tokens

- **Hallazgo [NEW][HIGH]:** token de escaneo se persiste en `config.json` en claro y aparece en logs de consola en algunos flujos.
- **Impacto:** secuestro de token y abuso de API de scans.
- **Mitigación actual:** expiración de token en backend.
- **Recomendación:** ocultar token en logs + cifrado local de token + rotación más corta.

## 4) Telemetry / PII leak

- **Hallazgo [NEW][HIGH]:** scanner recolecta y envía `machine_id`, `machine_name`, `ip_address`, `country`, `minecraft_username`, metadatos de sistema.
- **Impacto:** superficie regulatoria (GDPR/LGPD) y riesgo de sobreexposición.
- **Recomendación:** minimización por defecto, consentimiento explícito, retención definida.

## 5) Integridad de distribución (`ArgusScanner.exe`)

- **Estado actual:** pipeline de build y distribución automatizada; no se evidencia en docs públicas un hash SHA256 firmado por release para verificación manual de usuario final.
- **Hallazgo [NEW][MEDIUM]:** verificación de integridad del binario para usuario final es débil/no documentada.
- **Recomendación:**
  - publicar checksum SHA256 por release,
  - firmar release notes/checksum (GPG/Sigstore),
  - documento "cómo verificar binario" para staff.

## 6) Comunicación cliente -> server

- **Actual:** HTTPS y timeouts.
- **Riesgos residuales:**
  - [MEDIUM] sin pinning,
  - [MEDIUM] sin firma end-to-end de payload de scan,
  - [LOW/MEDIUM] exposición de token en endpoints o depuración local.

## Recomendaciones priorizadas (scanner)

1. Cifrar/pseudocifrar token local + no loguearlo en claro.
2. Publicar hashes firmados de release.
3. Añadir pinning opcional para despliegues enterprise.
4. Reducir PII enviada por defecto y documentar base legal.
5. Añadir detección de manipulación de `config.json` (checksum/HMAC local).
