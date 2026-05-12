# Feature storage patterns (Pack 48-H Round 5 · #137)

## Qué es una feature en ML

Representación numérica/categórica de señal derivada de datos crudos (ej. `violations_last_7d`, `avg_risk_score_30d`, `oracle_confidence_avg`).

## Patrones de almacenamiento

| Patrón | Descripción | Cuándo |
| --- | --- | --- |
| Wide table | Columnas por feature en `ai_player_profiles` | POC, pocas features |
| EAV (`feature_key`, `value`) | Flexible, queries más pesadas | Exploración |
| JSONB blob | `features JSONB` versionado | Medio volumen, schema evolutivo |
| Vector + metadata | `pgvector` + cols clave | embeddings |
| Offline store externo | Feast / DuckDB / Parquet en S3 | training a escala |

## Recomendación Argus (evolutiva)

1. **Fase A**: JSONB `feature_bundle_version` + `features` en tabla perfil con índice GIN selectivo.
2. **Fase B**: materializar features hot en columnas typed + MV refresh 5 min.
3. **Fase C**: export Parquet versionado para training (`training-data-versioning.md`).

## Versionado de bundle

```text
features_version INT NOT NULL DEFAULT 1
features JSONB NOT NULL
generated_at TIMESTAMPTZ NOT NULL
```

Permite A/B de modelos y rollback.

## Consistencia

- Features online deben poder regenerarse desde raw (`scans`, `violations`).
- No almacenar sólo score final sin trazabilidad si compliance lo exige.

## Referencias

- `docs/db/ml-data/online-vs-offline-features.md`
- `docs/db/postgres-topics/jsonb-deep.md`
