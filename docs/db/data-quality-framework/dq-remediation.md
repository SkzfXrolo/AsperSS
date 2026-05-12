# DQ remediation (Pack 48-H Round 6 · #158)

## Flujo

1. **Detect** (`dq-monitoring.md`).
2. **Triage**: ¿bug app? ¿bug data? ¿caso legítimo?
3. **Contain**: feature flag / pausa ETL si downstream contaminado.
4. **Fix raíz** en código.
5. **Backfill** filas afectadas (script idempotente).
6. **Postmortem** corto si HIGH.

## Patrones backfill

- UPDATE batched (`WHERE ctid IN (...) LIMIT 5000`).
- Reprocesar via outbox/replay.
- Reseed tabla derivada.

## Argus

Crear `scripts/db/remediation/` (futuro) por familia de problema. No incluido este Pack.

## Referencias

- `docs/db/cookbook/data-backfills.md`
