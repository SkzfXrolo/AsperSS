# Arrays in PostgreSQL (Pack 48-H Round 5 · #140)

## Declaración

```sql
SELECT ARRAY[1,2,3];
SELECT '{1,2,3}'::int[];
```

## Operadores útiles

| Op | Significado |
| --- | --- |
| `\|\|` | concatenar arrays |
| `@>` / `<@` | contención |
| `&&` | overlap |
| `unnest(arr)` | filas por elemento |

## Indexación

- GIN sobre columna `text[]` para búsquedas overlap/contención.
- Para arrays enormes, considerar tabla hija normalizada.

## Argus

- Tags de plugins, listas de reglas: `text[]` + GIN puede ser mejor que JSONB si estructura simple.

## Errores comunes

- Arrays multidimensionales rectangulares requeridos.
- 1-indexed en funciones SQL `array_position`.

## Referencias

- `docs/db/postgres-topics/jsonb-deep.md`
