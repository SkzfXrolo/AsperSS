# Data quality dimensions (Pack 48-H Round 6 · #158)

| Dimensión | Pregunta | Métrica típica |
| --- | --- | --- |
| Completeness | ¿Faltan valores requeridos? | % NOT NULL en cols obligatorias |
| Accuracy | ¿Valores correctos vs realidad? | comparación contra source-of-truth |
| Consistency | ¿Coherencia entre tablas/sistemas? | invariantes referenciales |
| Timeliness | ¿Frescos? | now() - max(created_at) |
| Uniqueness | ¿Sin duplicados indebidos? | count distinct vs total |
| Validity | ¿Conforme a reglas? | CHECK constraints, regex |

## Argus

Cada SLI mapea a una dimensión + tabla `data_quality_runs` registra outcome.

## Referencias

- `docs/db/data-observability.md` (Round 4)
- `docs/db/data-quality-framework/dq-checks-catalog.md`
