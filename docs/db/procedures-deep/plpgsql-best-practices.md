# PL/pgSQL best practices (Pack 48-H Round 5 · #143)

## Estilo

- `LANGUAGE plpgsql` explícito.
- Prefijo `argus_` para funciones globales Argus (ya usado en Round 4).
- Evitar `SELECT *` en variables RECORD salvo prototipos.

## Performance

- Minimizar `RAISE NOTICE` en hot paths.
- Preferir **SQL statements** set-based vs loops row-by-row.
- `STABLE`/`IMMUTABLE` cuando aplique para optimizar inlining.

## Seguridad

- `SECURITY INVOKER` por defecto.
- `SECURITY DEFINER` sólo con schema dedicado + `search_path` fijo (ver `security-definer.md`).

## Transacciones

- Funciones `VOLATILE` corren en transacción del caller; no `COMMIT` manual salvo procedures `PROCEDURE` PG11+ con cuidado extremo.

## Testing

- pgTAP + `scripts/db/test/test-functions.sql`.

## Referencias

- `docs/db/procedures-deep/error-handling.md`
- `docs/db/stored-procedures-vs-app.md` (Round 4)
