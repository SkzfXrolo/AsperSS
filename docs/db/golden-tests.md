# Golden schema tests (Pack 48-H Round 3 · #103)

## Idea

"Golden file testing" aplicado al schema de la base de datos. Mantener un archivo de referencia (`scripts/db/golden-schema.sql`) con el shape esperado y un test que falla cuando el actual diverge.

## Componentes

| Archivo | Rol |
| --- | --- |
| `scripts/db/golden-schema.sql` | Schema esperado (mantenido a mano) |
| `scripts/db/schema-drift-check.py` | Comparador automatizado (JSON in/out) |
| `tests/db/test_golden_schema.py` (futuro) | Test pytest que ejecuta el comparador contra DB efímera |

## Tests propuestos

### 1. `test_no_critical_drift`

Levanta DB efímera (PG en container), corre todas las migrations, dumpea schema, compara contra golden.

```python
def test_no_critical_drift(pg_ephemeral):
    cmd = [
        "python", "scripts/db/schema-drift-check.py",
        "--db-url", pg_ephemeral.url,
        "--expected", "scripts/db/golden-schema.json",
        "--ignore-extra-indexes",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    assert data["summary"]["critical"] == 0, data
    assert data["summary"]["high"] == 0, data
```

### 2. `test_pii_columns_classified`

Cargar `docs/db/data-classification.md` (table de columnas) y validar que cada columna PII-H/M existe en golden.

### 3. `test_all_tables_have_pk`

```python
def test_all_tables_have_pk(pg_ephemeral):
    cur = pg_ephemeral.cursor()
    cur.execute("""
        SELECT t.table_name
        FROM information_schema.tables t
        LEFT JOIN information_schema.table_constraints tc
          ON t.table_name = tc.table_name AND tc.constraint_type='PRIMARY KEY'
        WHERE t.table_schema='public' AND tc.constraint_name IS NULL;
    """)
    missing = [r[0] for r in cur.fetchall()]
    assert not missing, f"Tables without PK: {missing}"
```

### 4. `test_all_company_tables_have_company_id`

Política multi-tenant: cada tabla con dato de empresa debe tener `company_id NOT NULL`.

### 5. `test_no_phantom_references`

Ya escaló el bug F-007 (queries fantasma a `scan_verdicts`/`empresas`/`fecha`). El test:
- parsea `web_app/app.py` con AST,
- extrae todas las literales SQL,
- valida nombres de tabla/columna contra golden.

(Implementar en Round 4 si subagente D lo agenda.)

## Workflow al hacer cambios

1. Subagente D / dev hace migration Alembic.
2. Aplica en DB efímera.
3. `pg_dump --schema-only` → diff con `golden-schema.sql`.
4. Si OK semánticamente: actualiza `golden-schema.sql` y `golden-schema.json` (regenerable con `pg_dump | json-converter`).
5. Commit conjunto: migration + golden update.
6. CI corre `test_no_critical_drift` y debe pasar.

## Falsos positivos esperados

- Order de columnas (PG no garantiza orden estable). El comparador ignora orden.
- Default values con notación distinta (`'now'::timestamp` vs `CURRENT_TIMESTAMP`). Normalizar antes de comparar.
- Sequences auto-creadas (`scans_id_seq`). Excluir vía patrón.

## Generación automática (futuro)

`scripts/db/golden-export.py`:
1. Conecta a DB.
2. Dump structured (tablas, cols, índices, constraints).
3. Sort keys.
4. Output `golden-schema.json`.

Eso evita drift entre el `.sql` (formato humano) y el `.json` (formato máquina).

## Adopción

Round 3 (este Pack):
- [x] Crear `golden-schema.sql`.
- [x] Documentar tests en este archivo.

Round 4 (futuro):
- [ ] Generar `golden-schema.json` con script Python.
- [ ] Implementar tests pytest.
- [ ] Activar gate en CI.

## Anti-pattern a evitar

NO commitear el golden con `\d+` raw output de psql: cambia con cada versión PG (e.g. PG14 vs PG16 muestran columnas distintas). Usar siempre JSON estructurado.
