# Oracle decisions archival (Pack 48-H Round 5 · #147)

## Contexto

`ai_decisions_log` crece lineal con decisiones Oracle; retención legal vs costo.

## Estrategias

| Estrategia | Descripción |
| --- | --- |
| Partition weekly | drop partitions > N meses post-legal review |
| Tiered storage | hot PG 180d, cold Parquet S3 anonimizado |
| MV pre-aggregate | histogramas por versión modelo |

## Anonimización export

- Remover campos PII antes de mover a cold storage.

## Referencias

- `scripts/db/cleanup-policy-pack48.sql`
- `docs/db/dw-export-design.md`
