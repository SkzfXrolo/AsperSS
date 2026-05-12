# Error handling in functions (Pack 48-H Round 5 · #143)

## Bloques EXCEPTION

```sql
BEGIN
  -- work
EXCEPTION
  WHEN unique_violation THEN
    RAISE EXCEPTION 'duplicate key %', SQLERRM USING ERRCODE = '23505';
  WHEN OTHERS THEN
    RAISE NOTICE 'failed: %', SQLERRM;
    RAISE;
END;
```

## Mapping errores

- Usar `SQLSTATE` estándar para interoperabilidad con app.
- `RAISE EXCEPTION ... USING ERRCODE = 'P0001'` para errores de negocio custom.

## Logging

- `RAISE LOG` / `RAISE WARNING` con moderación (spam logs).
- Correlación: incluir `application_name` seteado por app.

## Argus

- Funciones de anonimización no deben tragar errores silenciosamente: preferir fail-fast en paths compliance.

## Referencias

- PostgreSQL docs: PL/pgSQL Error Reporting
