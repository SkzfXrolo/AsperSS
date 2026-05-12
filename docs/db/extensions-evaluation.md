# PostgreSQL extensions evaluation (Pack 48-H Round 3 · #96)

## Cuadro resumen

| Extension | Recomendación | Prioridad | Disponible en Render? | Costo install | Costo mantenimiento |
| --- | --- | --- | --- | --- | --- |
| `pg_stat_statements` | **HABILITAR YA** | P0 | sí (default) | trivial | nulo |
| `pgcrypto` | **HABILITAR YA** | P0 | sí | trivial | nulo |
| `pg_trgm` | habilitar | P1 | sí | trivial | bajo |
| `pgvector` | preparar | P2 | depende del tier | trivial | bajo |
| `pg_repack` | habilitar | P1 | parcial | medio (binarios) | medio |
| `pgaudit` | evaluar | P2 | dudoso | medio | medio |
| `pg_partman` | preparar | P2 | dudoso | medio | bajo |
| `pgbouncer` | **YA en roadmap** | P0 | externo | medio (config) | medio |
| `pg_cron` | habilitar si posible | P1 | no en todos los tiers | trivial | bajo |
| `postgis` | NO | — | sí | grande | grande |

Convención de prioridad: P0 = Pack 48, P1 = próximo trimestre, P2 = backlog.

---

## `pg_stat_statements` — P0 MUST HAVE

**Para qué**: top queries por tiempo/CPU/IO. Sin esto, no se puede priorizar optimizaciones.

**Instalar**:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
-- en postgresql.conf:
-- shared_preload_libraries = 'pg_stat_statements'
-- pg_stat_statements.max = 5000
-- pg_stat_statements.track = all
```

**Costos**: requiere restart (Render: ejecutar en ventana de mantenimiento).
**Maintenance**: rotar con `SELECT pg_stat_statements_reset()` post-deploy de cambios grandes.

**Uso**: ver `scripts/db/monitoring-queries.sql` (top queries).

---

## `pgcrypto` — P0

**Para qué**: hashing, column-level encryption.
**Uso en Argus**: hash de emails (`digest(email,'sha256')`), encrypt IPs sensibles, generar tokens criptográficos (`gen_random_bytes`).

**Instalar**:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

**Riesgos**:
- Decrypt en SQL expone la key al backup → preferir application-level encryption con KMS para PII crítica.
- Ver `encryption-strategy.md` para decisión final.

---

## `pg_trgm` — P1

**Para qué**: búsqueda "fuzzy" (LIKE '%foo%' barato con índice GIN trigram).
**Uso en Argus**: buscar jugadores por `player_name`, búsqueda en `staff_audit_log.action`.

**Instalar**:

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_player_name_trgm
    ON ai_player_profiles USING gin (player_name gin_trgm_ops);
```

**Costo**: índices GIN son ~3× más grandes que B-tree, builds más lentos. OK para tablas <10M.

---

## `pgvector` — P2 (preparar)

**Para qué**: storage y similarity search de embeddings (Oracle 2.0).
**Uso futuro**: vector(384) por scan/profile → KNN.

**Instalar**:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE ai_player_profiles ADD COLUMN behavior_vector vector(384);
CREATE INDEX idx_pp_vec_hnsw ON ai_player_profiles
    USING hnsw (behavior_vector vector_cosine_ops);
```

**Costos**:
- Render: revisar tier. AWS RDS lo soporta nativamente; Render PG depende de versión.
- Storage: 384×4B = 1.5KB por fila → 1.5GB por 1M filas.
- Index HNSW: alto consumo de RAM al build (~2× tamaño del index).

**Decisión**: **no activar todavía** hasta que Oracle 2.0 tenga producto definido.

---

## `pg_repack` — P1

**Para qué**: VACUUM FULL **sin** lock exclusivo. Lifesaver para bloat en tablas grandes.

**Instalar**: `apt-get install postgresql-15-repack` (host) o pedir a Render que lo habilite.

**Uso**:

```bash
pg_repack -h $PGHOST -U $PGUSER -d argus_prod -t scans --no-superuser-check
```

**Costo**: requiere disk ~2× tamaño de tabla durante repack. Lock corto en swap final.

---

## `pgaudit` — P2

**Para qué**: log estructurado de DDL/DML para compliance (SOC2/PCI).
**Uso Argus**: registrar cualquier `ALTER TABLE`, `GRANT`, `DELETE` sobre tablas sensibles.

**Costo**: aumenta volumen de logs ~10-30%. Logs van a `stderr` + log shipping.

**Recomendación**: evaluar cuando entremos a compliance certification.

---

## `pg_partman` — P2

**Para qué**: manejo automático de particiones (creación, retención).
**Uso Argus**: las tablas particionadas en #89 hoy se mantienen con función custom. `pg_partman` reemplaza eso con declarative config.

**Requisito**: Render debe permitirlo.
**Costo**: instalar + tabla `partman.part_config` + cron.

**Recomendación**: habilitar cuando #89 esté en prod y el cron custom dé problemas.

---

## `pg_cron` — P1

**Para qué**: scheduled jobs in-DB (no requiere cron del SO).
**Uso Argus**: refresh de MVs, retention (`DELETE FROM ai_decisions_log WHERE ...`), ETL stage trigger.

**Instalar**:

```sql
CREATE EXTENSION IF NOT EXISTS pg_cron;
```

**Limitación Render**: en algunos tiers no está disponible. Verificar; fallback = cron en worker dyno.

---

## `postgis` — NO

Argus no maneja geometría/coordenadas geográficas hoy. Activarlo introduce gran cantidad de dependencias y aumenta tamaño del clúster.

**Reevaluar** sólo si aparece feature de geo-fencing de servidores MC.

---

## `uuid-ossp` vs `gen_random_uuid()` — recordatorio

- En PG13+, `gen_random_uuid()` está built-in (vía `pgcrypto`). Preferir esto.
- `uuid-ossp` sólo si se necesitan v3/v5 (namespaces).

---

## Cómo aplicar

1. Crear PR / ticket pidiendo a Render que habilite `pg_stat_statements`, `pgcrypto`, `pg_trgm`.
2. Ventana de mantenimiento (restart): habilitar `shared_preload_libraries` y crear extensiones.
3. Verificar con `SELECT * FROM pg_extension;`.
4. Documentar en `migration-runbook.md`.

## Auditoría periódica

Mensual: revisar `pg_extension` vs lista esperada (golden test, ver `golden-schema.sql`).
