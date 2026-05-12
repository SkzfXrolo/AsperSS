# Pack 49 DB migration plan overview (Pack 48-H Round 5 · #149)

## Misión Pack 49 (DB track)

Establecer **cadena de ownership** del schema fuera de `app.py` guards, corregir **F-001**, habilitar **RLS** progresivo, y aplicar **índices críticos** con seguridad operativa.

## Entregables DB

| # | Entregable | Doc |
| --- | --- | --- |
| 1 | Alembic bootstrap + baseline | `alembic-bootstrap.md` |
| 2 | Migración `scans.company_id` + backfill | `F-001-fix.md` |
| 3 | RLS fase 1 (staging) | `rls-enablement.md` |
| 4 | Índices `CONCURRENTLY` prioridad HIGH | `index-additions.md` |
| 5 | CI `schema-drift-check` + pgTAP | `docs/db/testing/strategies.md` |

## Dependencias no-DB

- Subagente D: fixes código queries fantasma **F-007**.
- Legal: confirmar retención antes cleanup masivo.

## Criterios de salida

- Alembic `head` aplicado en staging sin error.
- `tenant-isolation-checks.sql` → 0 alertas críticas.
- p95 panel queries < baseline -10% (medido).

## Referencias

- `docs/db/migration-tooling-deep.md`
- `docs/db/findings-pack48.md`
