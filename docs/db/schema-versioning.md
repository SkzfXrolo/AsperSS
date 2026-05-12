# Schema versioning strategy (Pack 48-H Round 3 · #99)

## Modelo: SemVer aplicado al schema

```
MAJOR.MINOR.PATCH
  │     │     └── cambios sin impacto cliente (renombrar índice, comments)
  │     └────── cambios aditivos / no-breaking (nueva tabla, nueva columna NULL)
  └────────── cambios breaking (drop columna, cambio tipo, rename, NOT NULL en col existente)
```

Versión actual estimada al cierre Pack 48: **`0.48.0`** (hasta que F-001 cierre).

## Reglas de cambio

| Cambio | Categoría | Versión bump | Requiere migration script |
| --- | --- | --- | --- |
| Crear tabla nueva | aditivo | MINOR | sí |
| Agregar columna NULLABLE con default | aditivo | MINOR | sí |
| Agregar índice | aditivo | PATCH | sí (CONCURRENTLY) |
| Cambiar tipo de columna | breaking | MAJOR | sí + window |
| Renombrar columna | breaking | MAJOR | sí + dual-read window |
| Drop columna | breaking | MAJOR | sí + grace period |
| Drop tabla | breaking | MAJOR | sí + archivado previo |
| Cambiar default (sin tocar existentes) | aditivo | PATCH | sí (ALTER TABLE...DROP DEFAULT, ADD DEFAULT) |
| Crear/modificar trigger | depende | MINOR o MAJOR | sí |

## Política de deprecación

| Etapa | Duración mínima | Acción |
| --- | --- | --- |
| Anuncio | 1 sprint (~2 sem) | Doc, `MEJORAS.txt`, marca `@deprecated` en código consumer. |
| Dual-write | 1 sprint | App escribe en columna vieja Y nueva. |
| Dual-read | 1 sprint | App lee de la nueva si presente, sino fallback. |
| Single-read | 2 sprints | App sólo lee nueva. |
| Drop | tras 4-6 sprints totales | Migration que elimina la vieja. |

## Naming de migrations

Alembic: `versions/2026_05_12_1342-abcd1234_add_company_id_to_scans.py`.
Convención:

```
YYYY_MM_DD_HHMM-<short_id>_<verb>_<subject>.py
```

Verbos: `add_`, `drop_`, `rename_`, `alter_`, `backfill_`, `index_`, `partition_`.

## Migration testing (gates)

| Gate | Cómo |
| --- | --- |
| Sintaxis SQL | `alembic check` en CI |
| Up → Down → Up idempotente | `alembic upgrade head && alembic downgrade -1 && alembic upgrade head` (en CI con DB efímera) |
| Performance en prod-like | Aplicar contra snapshot de prod en staging, medir tiempo |
| No locks largos | `SET lock_timeout = '5s'` envuelve cada DDL |
| Rollback testeado | Crear data, downgrade, validar |

## Compatibility matrix app ↔ schema

| Componente | Lectura | Escritura |
| --- | --- | --- |
| `web_app` (Flask) | min schema X | min schema X |
| Plugin MC v1.0 | requiere campo `scan_token` (introducido en 0.32.0) | idem |
| Worker batch | min schema X-1 (puede correr en deploy intermedio) | min schema X-1 |
| Reportes externos / DW | min schema X-2 (lag aceptable) | n/a |

**Regla**: nunca hacer un deploy app que rompa workers de la versión anterior; rollback siempre debe ser posible 1 versión atrás.

## Visión de cambios pendientes (de findings Round 1-2)

| Finding | Tipo | Versión target |
| --- | --- | --- |
| F-001 add `scans.company_id` | MAJOR (eventualmente NOT NULL) | 1.0.0 |
| F-002 dedupe índices | PATCH | 0.49.x |
| F-003 unify `created_at` defaults | PATCH | 0.49.x |
| F-007 phantom tables/cols (`scan_verdicts`, `empresas`) | crítico, fix app code | 0.49.0 |

## Anuncio público de cambios

Para clientes con plugin MC custom o integraciones DW: nota de release con tabla.

```
### Schema 0.49.0 (Pack 49)
- ADD: scans.company_id INTEGER, NULLABLE for now
- ADD: index idx_scans_company_started
- DEPRECATE: nothing
- BREAK: nothing
- Migration time est: 2 min in maintenance window
```

## Migration testing checklist

- [ ] El script tiene `upgrade()` y `downgrade()`.
- [ ] Idempotente (`IF NOT EXISTS`, `IF EXISTS`).
- [ ] Probado en staging clone.
- [ ] Lock duración medida (<1s para ALTER típico).
- [ ] Documentado en `migration-runbook.md`.
- [ ] Verificado contra golden-schema (`docs/db/golden-tests.md`).
- [ ] CI pasa con DB efímera.
