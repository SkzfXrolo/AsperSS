# EAV pattern (Pack 48-H Round 6 · #157)

## Definición

`entity_id`, `attribute`, `value` — flexible pero costoso.

## Pros

- Atributos dinámicos sin migration.

## Cons

- Queries complejas (pivot).
- Tipado pobre (`value TEXT`).
- Performance pobre vs columnas tipadas.

## Alternativas mejores

- **JSONB** con esquema versionado.
- **Sparse tables** (NULLable columns) para atributos comunes.

## Argus

EAV **NO** recomendado. Si necesidad surge: JSONB + GIN selectivo (`postgres-topics/jsonb-deep.md`).

## Referencias

- `docs/db/anti-patterns.md`
