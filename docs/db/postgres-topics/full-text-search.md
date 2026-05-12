# Full-text search (FTS) (Pack 48-H Round 5 · #140)

## Pipeline básico

```sql
SELECT to_tsvector('english', 'Argus bans cheaters quickly') @@
       plainto_tsquery('english', 'ban cheater');
```

## Almacenamiento

| Estrategia | Descripción |
| --- | --- |
| Generated column | `tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', coalesce(title,'') \|\| ' ' \|\| coalesce(body,''))) STORED` |
| Índice GIN | `CREATE INDEX ON t USING gin(tsv);` |
| `jsonb_to_tsvector` | indexar campos JSON |

## Ranking

```sql
SELECT ts_rank_cd(tsv, query) AS rank
FROM doc, plainto_tsquery('english', 'oracle ban') query
WHERE tsv @@ query
ORDER BY rank DESC;
```

## Argus

- Búsqueda staff en notas/motivos: idioma `simple` si contenido multilenguaje mezclado.
- Evitar FTS sobre tablas masivas sin filtro `company_id` primero (índice compuesto).

## Referencias

- `docs/db/extensions-evaluation.md` (`pg_trgm` complemento fuzzy)
