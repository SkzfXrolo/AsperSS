# pgTAP framework (Pack 48-H Round 5 · #142)

## Qué es

[pgTAP](https://pgtap.org/) es framework de tests xUnit-like para PostgreSQL: `plan()`, `ok()`, `is()`, `has_table()`, `has_index()`, etc.

## Instalación (self-host / dev)

```sql
CREATE EXTENSION IF NOT EXISTS pgtap;
```

En managed DB: **REVIEW** si extensión permitida.

## Ejecución

```bash
pg_prove -U postgres -d argus_test scripts/db/test/*.sql
```

## Patrón mínimo

```sql
BEGIN;
SELECT plan(1);
SELECT has_table('public','scans');
SELECT * FROM finish();
ROLLBACK;
```

Usamos `ROLLBACK` final para no dejar objetos de test si el runner no aísla transacción.

## Integración CI

- Falla build si cualquier test falla.
- Paralelizar suites por archivo.

## Argus

- Priorizar tests que capturen regresiones multi-tenant y F-001 cuando se corrija.

## Referencias

- `scripts/db/test/test-schema.sql`
