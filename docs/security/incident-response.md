# Incident Response Playbook — Argus

## Objetivo

Estandarizar respuesta ante incidentes de seguridad en web_app, scanner, plugin y mobile.

## Roles sugeridos

- **Incident Commander (IC):** coordina y decide.
- **Tech Lead IR:** contención técnica.
- **Comms Lead:** comunicación interna/externa.
- **Forensics Lead:** preservación y análisis de evidencia.
- **Legal/Privacy Lead:** cumplimiento y notificaciones regulatorias.

## Flujo general (0-72h)

1. **Detección y triage**
   - clasificar severidad e impacto.
2. **Contención**
   - bloquear llaves/tokens/usuarios comprometidos.
3. **Erradicación**
   - remover vector raíz, rotar secretos.
4. **Recuperación**
   - restaurar servicio y monitorear recaída.
5. **Post-mortem**
   - RCA, acciones preventivas, due dates.

## Caso A: Data breach (PII/db leak)

- Activar war room.
- Congelar evidencia (logs, snapshots, hashes).
- Rotar secretos DB/API inmediatamente.
- Estimar alcance de datos afectados.
- Preparar notificación a clientes/regulador según jurisdicción.

## Caso B: Credenciales filtradas (staff/superadmin/plugin key)

- Revocar sesiones y tokens activos.
- Reset forzado de credenciales afectadas.
- Rotar plugin keys `argus_pk_*`.
- Buscar actividad anómala retrospectiva (lookback).

## Caso C: Plugin malicioso reportado / supply-chain sospechosa

- Suspender distribución automática.
- Verificar firma/hash de artefactos recientes.
- Rebuild limpio desde commit verificado.
- Publicar advisory y guía de remediación.

## Caso D: DoS sostenido

- Activar rate-limit estricto y WAF rules.
- Degradar features costosas (AI endpoints) temporalmente.
- Priorizar endpoints esenciales (health/auth/control).
- Coordinar escalado de infraestructura.

## Preservación de evidencia (mínimo)

- hora UTC de eventos,
- request IDs / actor IDs,
- hashes de binarios/configs,
- snapshots de logs inmutables.

## Plantilla breve post-mortem

- qué pasó,
- impacto real,
- causa raíz,
- qué funcionó / qué falló,
- acciones concretas (owner + fecha),
- evidencia de cierre y retest.
