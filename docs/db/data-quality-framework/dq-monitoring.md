# DQ monitoring (Pack 48-H Round 6 · #158)

## Cadencia

| Check | Frecuencia |
| --- | --- |
| timeliness | cada 1-5 min |
| volume / distribution | cada hora |
| uniqueness / FK integrity | nightly |
| accuracy comparativos | semanal |

## Persistencia

Tabla `data_quality_runs` (ver `data-observability.md`).

## Alerting

- `status=fail` → page si severity HIGH.
- `status=warn` con racha 3 runs → escalar.

## Dashboards

- Panel "DQ pass rate 7d" por check.
- Top failing checks por número filas afectadas.

## Argus

Job Python que orquesta SQL → DB → métricas. Esqueleto futuro en `scripts/db/auto-doc/` style.

## Referencias

- `docs/db/data-observability.md`
