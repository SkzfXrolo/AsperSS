# Secure SDLC (Argus)

## Fases y actividades de seguridad

## 1) Requirements

- clasificación de datos,
- requisitos de seguridad/compliance,
- abuse cases.

## 2) Design

- threat modeling,
- arquitectura zero-trust y controles de authz,
- decisiones de crypto/secret management.

## 3) Implementation

- secure coding standards,
- code review con checklist de seguridad,
- gestión segura de dependencias.

## 4) Testing

- SAST/DAST,
- fuzzing,
- tests de seguridad unit/integration.

## 5) Deploy

- firma de artifacts,
- IaC hardening,
- rollout con feature flags de seguridad.

## 6) Operations

- monitoreo y alertas,
- incident response,
- vuln management y patching SLA.

## Tooling mapping

- SAST: bandit/semgrep/gitleaks/pip-audit/safety
- DAST: nuclei
- SBOM: cyclonedx tools
- Compliance evidence: CI artifacts + audit logs
