# MongoDB → PostgreSQL (Pack 48-H Round 6 · #160)

## Modelado

- Cada colección suele mapear a tabla.
- Embedded documents → JSONB o tabla hija.
- Decidir per-collection.

## Pipeline

1. Export `mongoexport --jsonArray` o change stream.
2. Cargar a tabla staging `raw_<col> (id text, doc jsonb)`.
3. Transformar a tablas tipadas con SQL/dbt.

## Indexación equivalente

| Mongo | PG |
| --- | --- |
| Single-field btree | btree |
| Text index | tsvector + GIN |
| Geospatial 2dsphere | PostGIS |
| TTL index | partitioning por fecha + DROP partition |

## Argus

Sólo relevante si integramos data origen Mongo (no es el caso Pack 48).

## Referencias

- `docs/db/postgres-topics/jsonb-deep.md`
