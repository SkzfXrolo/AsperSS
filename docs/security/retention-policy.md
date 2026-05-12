# Data Retention Policy — Argus

## Política propuesta (baseline)

- **Scans crudos:** 90 días
- **AI predictions / ai_decisions:** 180 días
- **Audit logs:** 365 días
- **Ban records:** permanente con anonimización parcial tras 1 año

## Detalle por dominio

| Dataset | Retención | Acción al vencer |
|---|---:|---|
| `scans`, `scan_results` | 90d | delete o aggregate-only |
| `ai_decisions_log`, `ai_feedback` | 180d | delete/anonymize |
| `staff_audit_log` | 365d | redact + archive |
| plugin violations | 180d | aggregate + delete raw |
| tokens y metadata | TTL operativo + 90d audit | delete |
| ban history | indefinido | anonimizar PII >1y |

## Cleanup job design (cron diario)

Horario sugerido: `03:30 UTC` diario.

## Flujo

1. seleccionar registros vencidos por policy.
2. snapshot de métricas de borrado.
3. ejecutar borrado/anonimización en batches (p.ej. 1k rows).
4. registrar auditoría (tabla `retention_jobs`).
5. alertar si job falla.

## Requisitos técnicos

- idempotencia por job run,
- lock distribuido para evitar doble ejecución,
- dry-run mode con reporte previo,
- dashboard de cumplimiento de retención.

## Excepciones legales

- retención extendida por investigación activa, fraude o requerimiento legal.
- toda excepción debe tener `owner`, `justificación` y `expiry`.
