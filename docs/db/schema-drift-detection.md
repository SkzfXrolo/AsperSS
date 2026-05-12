# Schema drift detection (Pack 48-H Round 3 · #100)

## Problema

En Argus, hoy el schema se construye **lazy** desde `app.py` (`_plugin_schema_guard`, `init_*`). Si alguien:

1. Aplica un hotfix DDL en prod psql directo.
2. Cambia el código del `init_*` pero el deploy aún no llegó a algún ambiente.
3. Cambia el orden de columnas o tipo en SQLite vs PG.

…**el schema real diverge del esperado** y no nos enteramos hasta que un query falla.

## Definición de drift

Comparación entre **`actual`** (lo que PG/SQLite reportan ahora) y **`expected`** (lo que las migrations/golden definen).

| Tipo | Detección | Severidad |
| --- | --- | --- |
| Tabla extra | actual − expected | medio |
| Tabla faltante | expected − actual | **crítico** |
| Columna extra | actual.column ∉ expected | medio |
| Columna faltante | expected ∉ actual | **crítico** |
| Tipo distinto | actual.type ≠ expected.type | alto |
| NULLABLE distinto | actual ≠ expected | alto |
| Default distinto | actual ≠ expected | medio |
| Índice extra | actual − expected | bajo (informa) |
| Índice faltante | expected − actual | medio |
| Constraint extra | actual − expected | medio |
| Constraint faltante | expected − actual | alto |

## Estrategia

1. Cada release "tira" un **snapshot** del schema esperado (golden, ver `golden-schema.sql`).
2. CRON semanal corre `scripts/db/schema-drift-check.py` contra prod (read-only) y compara.
3. Si hay diff → alerta a Slack/PagerDuty.

## Inputs

- `--db-url` (read-only role).
- `--expected` archivo JSON con la forma esperada (generado por golden script).

## Outputs

- Exit code 0 si todo OK, 1 si hay drift.
- JSON estructurado en `stdout` con lista de diferencias.
- (opcional) `--report-slack-webhook URL` para postear.

## Run schedule

- **CI**: en cada PR que toca migrations, contra DB efímera.
- **Cron prod**: lunes 09:00 UTC.
- **Manual**: tras un incident para confirmar que prod = expected.

## False positives a manejar

1. Índices auto-creados por PG (e.g. PK index) que no están en migrations.
2. `pg_extension` schemas (timescale chunks, partman config).
3. Sequences gestionadas por `SERIAL` (auto-creadas).
4. Particiones dinámicas (creadas por cron mensual).

Solución: lista de **excludes** en `scripts/db/schema-drift-check.py` (`EXCLUDE_TABLE_PATTERNS`).

## Adopción

1. Round 3 entrega script y doc.
2. Subagente D / dev integra en CI con `pytest` job.
3. Habilitar cron una vez Alembic esté en producción (porque `expected` viene de Alembic state).

## Limitaciones

- No detecta **datos** corruptos, sólo schema.
- No detecta drift en **funciones / triggers** stored procedures (futuro Round 4).
- En multi-region, comparar contra **cada** replica.

## Ejemplo de output

```json
{
  "summary": { "missing_tables": 0, "extra_tables": 1, "type_mismatches": 2 },
  "details": [
    {
      "kind": "extra_table",
      "name": "tmp_migration_backup_2026_05_05"
    },
    {
      "kind": "type_mismatch",
      "table": "scans",
      "column": "verdict",
      "actual": "character varying(50)",
      "expected": "character varying(32)"
    },
    {
      "kind": "missing_column",
      "table": "scans",
      "column": "company_id"
    }
  ]
}
```

Ver `scripts/db/schema-drift-check.py` para implementación.
