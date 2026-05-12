# Logical replication conflict resolution (Pack 48-H Round 5 · #134)

## Contexto

En replicación lógica **unidireccional** (publisher → subscriber read-only) **no hay conflictos** de merge: el subscriber no escribe las mismas filas.

Los conflictos aparecen cuando:

1. **Multi-master lógico** (escritura en ambos lados en tablas replicadas).
2. **Failover** con promoción de subscriber que luego vuelve a sincronizar.
3. **Re-seed** manual en subscriber que colisiona con eventos entrantes.
4. **Triggers en subscriber** que insertan filas relacionadas con PK existente.

## Tipos de conflicto (subscriber apply)

| Tipo | Causa | Comportamiento default PG |
| --- | --- | --- |
| `insert_exists` | PK/unique ya existe | Error y pausa subscription (según versión/config) |
| `update_missing` | UPDATE sin fila destino | Puede error o skip según política |
| `update_deleted` | Race delete | Similar |
| `delete_missing` | DELETE idempotente | Suele ignorarse |

Consultar `conflict_table` / `subscription_conflict` en PG 16+ (evolución por versión — revisar docs de la versión desplegada).

## Estrategias recomendadas

### A. Evitar conflictos (preferido Argus)

- Subscriber **read-only** para roles de aplicación (`REVOKE INSERT/UPDATE/DELETE`).
- Procesos ETL en subscriber escriben en **schemas separados** (`analytics.*`) no publicados de vuelta.

### B. Source of truth único

- `company_id` + `id` compuesto como verdad en publisher; subscriber nunca genera IDs propios para mismas entidades.

### C. Bidireccional (no recomendado Pack 48-52)

Si se requiere active-active:

| Patrón | Descripción |
| --- | --- |
| Partition por región | Cada región escribe sólo su shard de `company_id`; sin overlap de PK. |
| CRDT / last-write-wins | Requiere columna `updated_at` y resolución en app; riesgo de pérdida. |
| Queue + serialización | Todas las escrituras pasan por un hub (Kafka) → un writer DB. |

### D. Resolución operativa tras error

1. `ALTER SUBSCRIPTION ... DISABLE`.
2. Inspeccionar `pg_stat_subscription` y logs del subscriber.
3. Corregir datos (DELETE duplicado, fix PK).
4. `ALTER SUBSCRIPTION ... ENABLE`.

## Argus: política sugerida

- **Prod → Analytics replica**: unidireccional, sin conflictos.
- **Prod → Prod DR** (futuro): unidireccional; en cutover, **promote** subscriber y **rebuild** publicación inversa si se necesita nueva topología.

## Referencias

- PostgreSQL manual: Logical Replication Restrictions
- `docs/db/multi-region-deep/active-active.md` (Round 5)
