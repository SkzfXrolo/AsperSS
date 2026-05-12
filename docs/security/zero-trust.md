# Zero-Trust Architecture (ZTA) for Argus

## Principios

- never trust, always verify,
- least privilege por identidad y contexto,
- assume breach.

## Aplicación en Argus

- cada request autenticada + autorizada explícitamente,
- no confiar por red interna/IP,
- micro-segmentación por servicio/tenant,
- auditoría continua de decisiones de acceso.

## Modelo objetivo (BeyondCorp-like)

1. identity-aware proxy para apps internas,
2. políticas contextuales (rol, device posture, riesgo),
3. secretos efímeros y rotación automática.

## Roadmap migración

- Fase 1: hardening authn/authz + anti-replay.
- Fase 2: mTLS + segmentación de servicios.
- Fase 3: policy engine central y acceso condicional.
- Fase 4: verificación continua y riesgo adaptativo.
