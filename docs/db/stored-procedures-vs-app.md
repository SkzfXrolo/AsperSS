# Stored procedures vs application logic (Pack 48-H Round 4 · #119)

## La pregunta

¿Dónde vive la lógica de negocio?

- **App**: Python/Flask gestiona reglas, DB es "dumb storage".
- **DB**: triggers, funciones PL/pgSQL, vistas, constraints; app sólo orquesta.
- **Híbrido** (recomendado): app maneja flujo y reglas mutables; DB se encarga de invariantes inviolables y validación física.

## Criterios para decidir

| Criterio | App | DB |
| --- | --- | --- |
| **Atomicidad multi-tabla** | difícil | nativo (single tx + trigger) |
| **Validación de invariantes** | duplicado en cada caller | una sola fuente |
| **Performance (evitar round-trips)** | depende | sí cuando hace 10 queries en una |
| **Testabilidad** | fácil con mocks | requiere DB efímera |
| **Versionado** | git diff legible | Alembic migration |
| **Refactor** | IDE friendly | manual |
| **Observabilidad / logs** | logger app | NOTICE / RAISE LOG en PL/pgSQL |
| **Reuso cross-app** | no (cada app reimplementa) | sí |
| **Vendor lock-in** | bajo | alto (PL/pgSQL no es portable) |

## Reglas pragmáticas para Argus

1. **Constraints siempre en DB** (NOT NULL, FK, CHECK, UNIQUE). Defensa última.
2. **Triggers sólo para invariantes y auditoría**, no para business logic.
3. **Cómputo derivado**: generated columns (`STORED`) en lugar de triggers manuales cuando se pueda.
4. **Funciones PL/pgSQL pequeñas como helpers** (e.g. `anonymize_ip`, `score_to_level`). Ver `scripts/db/functions/utility-functions.sql`.
5. **Lógica de negocio compleja → app**. Más fácil testear, deploy, observar.

## Argus position: "mostly app, some triggers for audit"

### Lógica que SÍ vive en DB

- `CHECK (risk_score BETWEEN 0 AND 100)`.
- `FOREIGN KEY ... ON DELETE CASCADE`.
- Trigger `staff_audit_trigger` que inserta en `staff_audit_log` post-modificación de tablas críticas.
- Trigger `tenant_isolation_trigger` (opcional) que valida `company_id` consistency entre tablas.
- Helper functions de **utilidad**: `argus_anonymize_ip()`, `argus_score_to_level()`.

### Lógica que vive en APP

- Reglas de scoring de scans.
- Permisos por rol (RBAC).
- Flujos de banneo (incluir notificación, webhook).
- Cobro / billing.
- Cualquier integración externa.

### Lo que pasa por DB sólo si performance lo justifica

- Cleanup de tablas viejas (`DELETE FROM ... WHERE created_at < ...`) puede ir a pg_cron en lugar de Python worker.
- ETL stages (#93) — SQL puro es más eficiente.

## Casos típicos analizados

### Caso A: validar que `scan.company_id == scan_tokens.company_id`

| Opción | Pro | Contra |
| --- | --- | --- |
| App: validar antes de INSERT | testeable | si app olvida, leak |
| DB: trigger BEFORE INSERT | enforce siempre | overhead, harder to debug |
| DB: CHECK constraint con subquery | imposible (no se permite) | — |
| App + tenant-isolation-checks.sql nightly | balance | detección post-facto |

**Argus**: app valida + nightly check. Si subiera el costo de leaks (compliance), añadir trigger.

### Caso B: invalidar caché Redis cuando cambia `scan`

| Opción | Pro | Contra |
| --- | --- | --- |
| App: después de COMMIT, llamar redis | controlado | si COMMIT pasa y luego app crashea, cache stale |
| DB: trigger AFTER COMMIT + LISTEN | atómico | requiere worker LISTEN; vendor lock |
| CDC layer (#92) | desacoplado | infra extra |

**Argus**: NOTIFY post-trigger + listener app. Plan en `cdc-design.md`.

### Caso C: calcular `verdict` desde violations

| Opción | Pro | Contra |
| --- | --- | --- |
| App: lógica Python en `argus_ai_*.py` | testable, iterable | dispersa, distintos workers reimplementan |
| DB function `argus_compute_verdict(scan_id)` | una fuente | difícil de versionar |
| Generated column | impracticable (depende de varias tablas) | — |

**Argus**: app, hoy. Si la lógica se estabiliza y se reusa cross-region, migrar a DB function.

## Patrones para minimizar dolor cuando usamos DB logic

1. **Versionar funciones** en `scripts/db/functions/*.sql`, incluir en migrations.
2. **Naming**: prefijo `argus_` para distinguir de funciones built-in.
3. **No DDL en funciones** (excepción).
4. **Tests con pgTAP** o queries fixture.
5. **Logs**: usar `RAISE NOTICE` (visible al cliente) o `RAISE LOG` (sólo log).
6. **Idempotencia**: `CREATE OR REPLACE FUNCTION` siempre.

## Anti-patterns

1. ❌ Triggers que envían HTTP a APIs externas (acoplan latencia DB).
2. ❌ Stored procs de 500 líneas (mover a app).
3. ❌ Funciones que asumen el current_user (rompen con conexión pool).
4. ❌ Mezclar reglas críticas (auth) en triggers (más difícil auditar).
5. ❌ Función PL/pgSQL para "evitar tener que escribir SQL" — es SQL igual, menos legible.

## Tooling recomendado

- **pgTAP** para tests de funciones/triggers.
- **plpgunit** alternativa más ligera.
- **plprofiler** para perf de funciones largas.
- **plpgsql_check** linter para PL/pgSQL.

## Roadmap Argus

| Pack | Acción |
| --- | --- |
| 49 | Adoptar Alembic + versionar las funciones existentes |
| 49 | Crear `argus_anonymize_ip`, `argus_score_to_level`, `argus_hash_pii` (Round 4 #120) |
| 50 | Trigger `staff_audit_log` automation (Round 4 #120) |
| 51 | Evaluar trigger tenant_isolation tras F-001 |
| 52+ | Revisar si alguna lógica del app justifica mover a DB |

## Referencias

- `scripts/db/functions/utility-functions.sql` (#120)
- `scripts/db/functions/triggers.sql` (#120)
- `testing-strategies.md` (#123)
