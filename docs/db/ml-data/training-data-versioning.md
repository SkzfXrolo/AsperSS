# Training data versioning (Pack 48-H Round 5 · #137)

## Objetivo

Reproducir entrenamientos Oracle / modelos auxiliares: mismo **dataset_id** → mismas métricas (dentro de variancia estadística).

## Capas

| Capa | Implementación sugerida |
| --- | --- |
| Raw snapshot | `pg_dump --table=ai_decisions_log --where="created_at between ..."` o export S3 |
| Curated dataset | dbt model materializado con hash |
| Manifest | `dataset_manifest` tabla con `git_sha`, `sql_hash`, `row_count`, `min_ts`, `max_ts` |

## Tabla manifest (ejemplo conceptual)

| Columna | Tipo |
| --- | --- |
| `dataset_id` | UUID PK |
| `name` | TEXT |
| `created_at` | TIMESTAMPTZ |
| `source_query_hash` | TEXT |
| `row_count` | BIGINT |
| `label_distribution` | JSONB |
| `pii_policy` | TEXT |

## Lineage

Integrar con OpenLineage o simple `parent_dataset_id` para transforms.

## Argus

- Cada release modelo Oracle referencia `dataset_id` en tabla `model_registry` (futuro).
- No mezclar datos pre/post cambio de definición de `risk_score` sin etiquetar versión.

## Referencias

- `docs/db/ml-data/ground-truth-labels.md`
- `docs/db/etl-pipeline-design.md`
