# Reporting layer (Pack 48-H Round 4 · #121)

## Misión

Centralizar las queries de reporte fuera de `app.py`. Tres beneficios:

1. **Reuso** entre web, CLI y exports CSV.
2. **Testabilidad** (pueden correrse en CI con seed).
3. **Performance**: vivir como **views** o queries optimizadas; el optimizador planifica una sola vez.

## Ubicación

```
scripts/db/reports/
├── monthly-summary.sql      ← resumen mensual por empresa
├── incident-report.sql      ← decisiones Oracle HIGH/CRITICAL
├── usage-report.sql         ← uso para billing
└── compliance-report.sql    ← DSAR / GDPR
```

Cada archivo es **ejecutable directamente con psql** (cuando se pasa el parámetro requerido) y deja vista o tabla temp para consumo externo.

## Convención de parámetros

Como SQL pure no acepta argumentos, usamos:

- variables psql (`\set company_id 14`)
- vistas parametrizadas via function (`SELECT * FROM report_monthly(14, '2026-04')`)

Recomendado para Argus: **functions** que devuelven sets. Más fáciles de consumir desde app vía SQLAlchemy.

## Distribución de outputs

| Reporte | Frecuencia | Destinatario | Formato |
| --- | --- | --- | --- |
| monthly-summary | 1° del mes | Founder + customer | PDF + CSV |
| incident-report | semanal | Tech Lead | dashboard |
| usage-report | diario | Billing | API JSON |
| compliance-report | on-demand (DSAR) | Legal | CSV anonimizado |

## Quality gates de reportes

- Cada reporte tiene una **versión** comentada en el header.
- Cambios → nueva versión, no editar in-place (subscribers necesitan estabilidad).
- Tests: snapshot del output contra seed dataset.

## Roadmap

| Pack | Acción |
| --- | --- |
| 49 | Mover reportes hardcoded de `app.py` a `scripts/db/reports/` |
| 50 | Endpoint `/api/reports/<name>` que ejecuta archivo |
| 51 | Email + PDF render |
| 52 | Customer self-service reporting |

## Ver también

- `scripts/db/reports/*.sql` — las 4 queries.
- `dw-export-design.md` — para reportes muy pesados, mover a DW.
- `query-performance.md` (Round 2) — optimización.
