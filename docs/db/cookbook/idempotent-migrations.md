# Idempotent migrations (Pack 48-H Round 6 · #165)

## Por qué

Re-correr la misma migration no debe fallar ni duplicar efectos.

## Patrones

- `CREATE TABLE IF NOT EXISTS`.
- `CREATE INDEX IF NOT EXISTS`.
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
- `INSERT ... ON CONFLICT DO NOTHING`.
- `DO $$ BEGIN IF NOT EXISTS (...) THEN ... END IF; END $$;` para casos complejos.

## Alembic

- Cada revision sólo se aplica una vez (tabla `alembic_version`).
- Aun así, escribir con guardas resilientes para re-runs accidentales o ambientes mixtos.

## Argus

Toda migration nueva debe pasar el patrón "re-run sin efecto" en CI.

## Referencias

- `docs/db/migration-tooling-deep.md`
