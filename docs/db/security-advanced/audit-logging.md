# Audit logging strategies (Pack 48-H Round 5 · #146)

## Capas

| Capa | Herramienta |
| --- | --- |
| DDL | event triggers (si permisos) |
| DML selectivo | triggers row audit |
| Sesión | `log_connections`, `log_disconnections` |
| Compliance | `pgaudit` (si extensión disponible) |

## Correlación

- Incluir `application_name`, `request_id` vía `SET`.

## Retención

- Hot 30d logs, cold 1y compliance.

## Argus

Render sin pgaudit → combinar triggers + central log sink.

## Referencias

- `docs/db/triggers-deep/audit-triggers.md`
- `docs/db/observability/log-analysis.md`
