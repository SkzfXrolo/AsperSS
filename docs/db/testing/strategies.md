# DB testing strategies (Pack 48-H Round 5 · #142)

Este documento complementa `docs/db/testing-strategies.md` (Round 4) con foco en **layout de repo** `docs/db/testing/` + scripts `scripts/db/test/`.

## Pirámide

| Nivel | Herramienta | Qué valida |
| --- | --- | --- |
| Schema | pgTAP + `test-schema.sql` | tablas, columnas, índices críticos |
| Migrations | `test-migrations.sql` + CI alembic | upgrade/downgrade idempotente |
| Funciones/triggers | `test-functions.sql` | comportamiento PL/pgSQL |
| Data quality | `data-quality.sql` | invariantes |
| Load | `scripts/db/stress-test/*` | límites sistema |

## CI recomendado

1. Spin Postgres efímero (testcontainers).
2. `psql -f scripts/db/seed-data.sql` (opcional).
3. `pg_prove -d $DB scripts/db/test/*.sql` o `psql -v ON_ERROR_STOP=1 -f ...` si pgTAP no instalado (ver notas en SQL).

## Convenciones

- Un archivo SQL por dominio de test.
- Tests deben **SKIP** si prereq no existe (extensiones, tablas legacy).

## Referencias

- `docs/db/testing/pgtap.md`
- `docs/db/golden-tests.md`
