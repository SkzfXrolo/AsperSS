# Alembic bootstrap (Pack 49) (Pack 48-H Round 5 · #149)

## Resumen

Pasos concretos para inicializar Alembic en el repo Argus. Detalle amplio en `scripts/db/alembic-bootstrap.md` (Round 2) y `docs/db/migration-tooling-deep.md` (Round 4).

## Secuencia mínima

1. `pip install "alembic>=1.13" "sqlalchemy>=2.0"`
2. `alembic init migrations`
3. Configurar `sqlalchemy.url` desde env (`DATABASE_URL` staging).
4. Importar `MetaData` vacío o reflejado.
5. `alembic revision -m "baseline pack49" --autogenerate` → **revisar manual**.
6. `alembic stamp head` en DB existente tras validar equivalencia schema.

## Convención commits

- Prefijo `Pack49-DB:` en mensajes de migración (fuera de Pack48-H pero anotado aquí).

## Referencias

- `scripts/db/alembic-bootstrap.md`
- `docs/db/migration-tooling-deep.md`
