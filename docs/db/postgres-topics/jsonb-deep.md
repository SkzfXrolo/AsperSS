# JSONB deep dive (Pack 48-H Round 5 · #140)

## Tipos y literales

```sql
SELECT '{"a":1}'::jsonb;
SELECT jsonb_build_object('company_id', 42, 'tags', ARRAY['x','y']);
```

## Indexación

| Índice | Uso |
| --- | --- |
| GIN default `jsonb_ops` | `@>`, `?`, `?&`, `?\|` |
| GIN `jsonb_path_ops` | más compacto si sólo `@>` |
| `expression` index | `(payload->>'status')` equality frecuente |
| `jsonb_to_tsvector` | FTS sobre JSON |

Ejemplo contenido:

```sql
CREATE INDEX idx_scan_meta ON scans USING gin ((metadata->'flags') jsonb_path_ops);
```

## Operadores clave

- `@>` contención.
- `->` devuelve jsonb; `->>` texto.
- `#>` path array.

## Rendimiento

- Evitar cast masivo `::text` en columnas grandes sin índice.
- `jsonb_each` expande → costoso en millones de filas.

## Argus

- `violations` / `scan` payloads: documentar schema JSON versionado (`features_version` pattern en ML doc).

## Referencias

- `docs/db/ml-data/feature-storage.md`
- `docs/db/performance/index-strategies.md`
