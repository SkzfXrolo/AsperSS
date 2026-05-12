# Ground truth labels storage (Pack 48-H Round 5 · #137)

## Definición

**Ground truth** = verdad supervisada para evaluar modelos (ej. staff confirma ban correcto/incorrecto, appeal outcome).

## Modelo de datos sugerido

Tabla `ml_labels` (conceptual):

| Columna | Tipo | Notas |
| --- | --- | --- |
| `label_id` | UUID PK | |
| `entity_type` | TEXT | `scan`, `player`, `oracle_decision` |
| `entity_id` | UUID/BIGINT | FK lógica |
| `label` | TEXT / JSONB | clase o rubrica |
| `labeler_id` | INT | staff user |
| `confidence` | NUMERIC | confianza del labeler |
| `created_at` | TIMESTAMPTZ | |
| `expires_at` | TIMESTAMPTZ NULL | si labels temporales |

## Integridad

- UNIQUE parcial por `(entity_type, entity_id)` donde `expires_at IS NULL` (último label vigente).
- Auditoría: append-only + `supersedes_label_id`.

## Sesgo y balance

- Monitorear distribución de labels por `company_id` y `labeler_id`.
- Alertas si un labeler produce >X% de una clase.

## Argus

- Conectar labels con `ai_decisions_log.id` para evaluar precision/recall por versión modelo.
- Anonimizar PII en snapshots exportados.

## Referencias

- `docs/db/ml-data/training-data-versioning.md`
- `docs/db/data-classification.md`
