# Security Roadmap 2026 (12 meses)

## Q1 (Fundaciones)

- eliminar secretos hardcodeados y rotación inicial completa.
- desplegar anti-replay HMAC en plugin/scanner.
- cerrar endpoints debug/sensibles en producción.
- baseline SAST/SCA en PR.

## Q2 (Hardening técnico)

- cert pinning en scanner/plugin/android.
- CSRF completo + SameSite/headers endurecidos.
- reintroducir obfuscación Android release.
- controles de rate-limit por costo para IA.

## Q3 (Compliance y privacidad)

- DSAR endpoints (`export/delete/info`) en producción.
- política formal de retención + cron de limpieza.
- ROPA/DPIA y documentación legal-operativa.
- programa bug bounty privado controlado.

## Q4 (Madurez avanzada)

- signing de artefactos con cosign/sigstore.
- SBOM obligatorio por release + Dependency-Track.
- tabletop exercises de incident response.
- pentest externo anual + cierre de findings.

## Métricas de éxito

- MTTR security incidents,
- porcentaje de hallazgos críticos cerrados <30 días,
- cobertura de tests de seguridad,
- cumplimiento de rotación de secretos.
