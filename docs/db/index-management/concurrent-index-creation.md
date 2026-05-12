# CREATE INDEX CONCURRENTLY (Pack 48-H Round 6 · #155)

## Por qué

`CREATE INDEX CONCURRENTLY` permite construir el índice **sin bloquear writes** (toma `ShareUpdateExclusiveLock` en vez de `ShareLock`).

## Costos

- Tarda más (2 scans).
- No funciona dentro de transacción → Alembic config `transactional_ddl = False` por migration.
- Si falla → índice en estado `INVALID` (`pg_index.indisvalid = false`); requiere `DROP INDEX CONCURRENTLY` + reintento.

## Patrón seguro

```sql
SET lock_timeout = '5min';
CREATE INDEX CONCURRENTLY idx_x ON scans(company_id, created_at DESC);
ANALYZE scans;
```

## Verificación post-build

```sql
SELECT relname, indexrelname, indisvalid
FROM pg_stat_user_indexes JOIN pg_index USING (indexrelid)
WHERE indexrelname = 'idx_x';
```

## Argus

Toda migration de índice en prod usa CONCURRENTLY salvo tabla muy chica.

## Referencias

- `docs/db/migration-tooling-deep.md`
- `docs/db/pack49-migration-plan/index-additions.md`
