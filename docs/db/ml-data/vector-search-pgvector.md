# pgvector for embeddings (Pack 48-H Round 5 · #137)

## Qué resuelve

`pgvector` almacena **embeddings** (vectores float) y soporta índices ANN (IVFFlat/HNSW en versiones recientes) para similitud coseno/L2/IP.

## Casos Argus

- **Oracle 2.0**: similaridad de historial de chat / descripciones de violación.
- **Clustering** de jugadores por comportamiento.
- **Detección duplicados** en reportes staff.

## DDL ilustrativo (no ejecutar en prod sin review)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE ai_player_profiles ADD COLUMN embedding vector(1536);
CREATE INDEX ON ai_player_profiles USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

## Limitaciones managed

Render puede **no** ofrecer `pgvector` en todos los tiers (`extensions-evaluation.md`). **REVIEW** antes de diseñar dependencia dura.

## Alternativas

- Embeddings en objeto storage + FAISS en servicio ML.
- ClickHouse / specialized vector DB si QPS similitud muy alto.

## Operación

- Reindex tuning: `lists` vs recall/latency.
- Normalizar vectores si métrica es coseno.

## Referencias

- `docs/db/extensions-evaluation.md`
- `docs/db/ml-data/feature-storage.md`
