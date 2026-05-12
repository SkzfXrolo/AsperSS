# Transaction control in procedures (Pack 48-H Round 5 · #143)

## Procedures vs functions (PG11+)

- `CREATE PROCEDURE` puede hacer `COMMIT`/`ROLLBACK` internos (por batches).
- `CREATE FUNCTION` tradicional **no** debe hacer commit explícito (error en muchas versiones/contextos).

## Patrón batch

```sql
CREATE PROCEDURE argus_archive_batch()
LANGUAGE plpgsql AS $$
DECLARE i int := 0;
BEGIN
  LOOP
    DELETE FROM big WHERE created_at < now() - interval '1 year' AND ctid IN (
      SELECT ctid FROM big WHERE created_at < now() - interval '1 year' LIMIT 5000
    );
    GET DIAGNOSTICS i = ROW_COUNT;
    EXIT WHEN i = 0;
    COMMIT;  -- procedure only
  END LOOP;
END$$;
```

## Riesgos

- Rompe atomicidad del caller si no documentado.
- Interacción con savepoints compleja.

## Argus

- Archival/cleanup masivo mejor en job externo con `DELETE ... LIMIT` + transacciones cortas, o procedure documentada.

## Referencias

- `docs/db/migration-tooling-deep.md` (batches)
