# DSAR Workflow (GDPR/LGPD)

## Endpoints propuestos

- `GET /api/me/processing-info`
- `GET /api/me/export`
- `DELETE /api/me/data`

## Flujo operativo

1. Usuario autenticado solicita acción DSAR.
2. Se dispara verificación secundaria por email.
3. Se aplica cooldown anti-abuso de 24h.
4. Sistema crea ticket DSAR con estado:
   - `pending_verification`
   - `verified`
   - `in_progress`
   - `completed`
   - `rejected`
5. Resultado:
   - export ZIP firmado temporal (expira 24h), o
   - soft-delete + anonimización en 30 días + hard-delete posterior.

## Export (`GET /api/me/export`)

Debe incluir:

- perfil de cuenta,
- scans asociados,
- feedback/verdicts del usuario,
- logs auditables relevantes.

Formato:

- ZIP con JSON por dominio (`profile.json`, `scans.json`, etc.).

## Right to be forgotten (`DELETE /api/me/data`)

Modelo recomendado:

- `T0`: marcar cuenta `deletion_requested`.
- `T+30d`: hard delete de campos personales (o anonimización irreversible).
- conservar solo metadatos mínimos legales/anti-fraude bajo base legal documentada.

## Audit trail obligatorio

Registrar por cada DSAR:

- `request_id`
- `user_id`
- `action_type` (`export`/`delete`/`info`)
- timestamps y actor ejecutor
- resultado y motivo de rechazo (si aplica)

## SLA recomendado

- acuse de recibo: <=72h
- resolución estándar: <=30 días
- extensión justificada: hasta 60 días (con notificación).
