# Index types in PostgreSQL (Pack 48-H Round 6 · #155)

| Tipo | Casos típicos | Notas |
| --- | --- | --- |
| **B-tree** (default) | equality + range, ORDER BY | el más usado |
| **Hash** | equality estricta | poco usado vs B-tree |
| **GIN** | jsonb `@>`, arrays, FTS | grande pero potente |
| **GiST** | geo, FTS, rangos | extensible |
| **SP-GiST** | datos no balanceados (trie) | nicho |
| **BRIN** | grandes tablas append-only por rango (timestamp) | ínfimo tamaño |

## Cuándo cada uno

- B-tree: `(company_id, created_at DESC)` panel queries.
- GIN: `payload @>` y FTS (`to_tsvector`).
- BRIN: `created_at` en tablas masivas particionadas → respaldo barato.
- GiST/SP-GiST: poco aplicable a Argus core actual.

## Argus

Default B-tree; GIN para JSONB hot; BRIN como complemento en particiones grandes.

## Referencias

- `docs/db/index-management/index-on-expression.md`
- `docs/db/performance/index-strategies.md`
