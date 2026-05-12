# PostgreSQL log analysis (Pack 48-H Round 5 · #138)

## Objetivos

- Detectar **queries lentas**, **deadlocks**, **checkpoint warnings**, **connection storms**.
- Correlacionar con deploys (`correlation_id` en app logs si existe).

## Qué loguear (self-host / configurable)

```text
log_line_prefix = '%m [%p] %q%u@%d '
log_min_duration_statement = 500ms   # ajustar
log_lock_waits = on
log_checkpoints = on
log_connections = on
log_disconnections = on
log_statement = 'ddl'                # evitar PII en data statements
```

## Render

Acceso típico vía **Render Logs** o integración Datadog/Logtail. Detalle limitado vs self-host.

## PgBadger

Ver `docs/db/pgbadger-guide.md` y `scripts/db/pgbadger/run-analysis.sh`.

## Queries comunes en Loki/ELK

- Top errores: `ERROR` lines count by fingerprint.
- Slowest normalized query: parse duration field.

## Retención

Balance costo vs investigación incidentes: 7–30 días hot, archive cold.

## Privacidad

No loguear payloads completos de columnas PII; usar parámetros bind redacted.

## Referencias

- `docs/db/security-advanced/audit-logging.md`
- `docs/db/data-classification.md`
