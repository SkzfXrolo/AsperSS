# Pack 48-H · Grand Summary — DB documentation index

Índice maestro de toda la documentación y scripts de DB producidos en Pack 48 por el subagente H (rounds 1-3).

Versión: 0.48.0 · DBA reviewer: pendiente.

---

## 1. Referencia del schema (qué tenemos hoy)

| Doc | Propósito |
| --- | --- |
| [`schema-pack48.md`](schema-pack48.md) | Tabla-por-tabla, columnas, tipos, índices, función Python de origen |
| [`schema-evolution.md`](schema-evolution.md) | Cambios por Pack (32→48), breaking changes |
| [`er-diagram.md`](er-diagram.md) | ERD Mermaid agrupado por dominio, leyenda sensibilidad |
| [`findings-pack48.md`](findings-pack48.md) | 25 hallazgos con severidad (3 HIGH, 9 MED, 6 LOW + nuevos) |

## 2. Diseño avanzado

| Doc | Tema |
| --- | --- |
| [`partitioning-design.md`](partitioning-design.md) | Particionado de `scans`, `ai_decisions_log`, `staff_audit_log` |
| [`materialized-views.md`](materialized-views.md) | 4 MVs propuestas + refresh strategy |
| [`connection-pool.md`](connection-pool.md) | PgBouncer + SQLAlchemy pool |
| [`cdc-design.md`](cdc-design.md) | LISTEN/NOTIFY + logical replication |
| [`etl-pipeline-design.md`](etl-pipeline-design.md) | Raw → Stg → Cln → Agg |
| [`dw-export-design.md`](dw-export-design.md) | Export a DW analítico |

## 3. Performance & escalado

| Doc | Tema |
| --- | --- |
| [`query-performance.md`](query-performance.md) | Audit de las 30 queries del panel |
| [`read-replicas-design.md`](read-replicas-design.md) | Cuándo y cómo agregar replicas |
| [`sharding-design.md`](sharding-design.md) | Sharding por `company_id` / `created_at` |
| [`multi-region.md`](multi-region.md) | Active-passive multi-region |
| [`timescaledb-evaluation.md`](timescaledb-evaluation.md) | NO migrar todavía, criterios para reevaluar |
| [`extensions-evaluation.md`](extensions-evaluation.md) | 10 extensiones PG candidatas |

## 4. Seguridad & privacidad

| Doc | Tema |
| --- | --- |
| [`encryption-strategy.md`](encryption-strategy.md) | At-rest, in-transit, columnar PII |
| [`data-classification.md`](data-classification.md) | PII-H/M/L + INT-B/O + PUB |
| [`security-hardening.md`](security-hardening.md) | pg_hba, roles, RLS, REVOKE, pgaudit |

## 5. Operaciones (DBA)

| Doc | Tema |
| --- | --- |
| [`migration-runbook.md`](migration-runbook.md) | Aplicar cambios en producción |
| [`migration-tool-comparison.md`](migration-tool-comparison.md) | Alembic vs Flyway vs Sqitch |
| [`schema-versioning.md`](schema-versioning.md) | SemVer + deprecation policy |
| [`schema-drift-detection.md`](schema-drift-detection.md) | Detectar divergencia actual vs esperado |
| [`golden-tests.md`](golden-tests.md) | Snapshot testing del schema |
| [`zero-downtime-upgrade.md`](zero-downtime-upgrade.md) | PG major upgrade con logical replication |
| [`dba-runbook.md`](dba-runbook.md) | Procedures cotidianas (VACUUM, REINDEX, etc.) |
| [`on-call-playbook.md`](on-call-playbook.md) | Pages, escalation, postmortem |
| [`edge-cases-playbook.md`](edge-cases-playbook.md) | Deadlocks, bloat, disk full, corruption |
| [`disaster-playbook.md`](disaster-playbook.md) | 7 escenarios P0 |

## 6. Confiabilidad & DR

| Doc | Tema |
| --- | --- |
| [`backup-strategy.md`](backup-strategy.md) | RPO/RTO, retention, GPG |
| [`dr-drill-plan.md`](dr-drill-plan.md) | Drill mensual |

## 7. Observabilidad

| Doc | Tema |
| --- | --- |
| [`dashboards-spec.md`](dashboards-spec.md) | Grafana — Overview & Capacity |

## 8. Costos & estrategia

| Doc | Tema |
| --- | --- |
| [`cost-optimization.md`](cost-optimization.md) | Acciones para reducir gasto |
| [`cost-forecast.md`](cost-forecast.md) | Modelo 12 meses |
| [`schema-2027-vision.md`](schema-2027-vision.md) | Visión 12+ meses del schema |

---

## Scripts (`scripts/db/`)

| Script | Uso |
| --- | --- |
| `additional-indexes.sql` | 28 índices recomendados (no duplicar ai_maintenance) |
| `cleanup-policy-pack48.sql` | DELETE batched para retention |
| `integrity-checks.sql` | 25 invariantes para validar |
| `explain-templates.sql` | 30 EXPLAIN ANALYZE listos |
| `monitoring-queries.sql` | ~20 queries de observabilidad |
| `tenant-isolation-checks.sql` | 15 checks multi-tenant |
| `data-quality.sql` | 20 invariantes de calidad |
| `dw-export.sql` | Vistas anónimas para DW |
| `partition-migration.sql` | Migración a particiones declarativas |
| `materialized-views.sql` | 4 MVs + helper refresh |
| `pgbouncer.ini` | Configuración PgBouncer |
| `etl-stages.sql` | Stages ETL + funciones |
| `schema-drift-check.py` | CI/cron diff actual vs esperado |
| `seed-data.sql` | Seed mínimo (1 company, 100 scans) |
| `synthetic-data-generator.py` | Generador masivo para staging |
| `golden-schema.sql` | Schema esperado para comparación |
| `cost-projection.py` | Proyección de costos 12m |
| `backup-automation.sh` | pg_dump + GPG + S3 |
| `alembic-bootstrap.md` | Setup inicial Alembic |

---

## Hallazgos críticos pendientes (escalados a otros subagentes)

| ID | Severidad | Resumen | Owner |
| --- | --- | --- | --- |
| F-001 | **HIGH** | `scans.company_id` referenciado pero no existe | D |
| F-007 | **HIGH** | Queries fantasma en app.py L810-828 (`fecha`, `scan_verdicts`, `empresas`) | D |
| F-005/F-006 | MEDIUM | Cascades faltantes en `user_sessions`, `oauth_tokens` | D |
| F-002 | LOW | Índices duplicados | H futuro |

Ver `findings-pack48.md` para el detalle completo de los 25 hallazgos.

## Top-5 recomendaciones (priorizadas)

1. **Aplicar F-001** (agregar `scans.company_id`) — bloquea casi todo lo demás (RLS, sharding, MVs por tenant, particionado limpio).
2. **Adoptar Alembic** ya en Pack 49 — sin migrations versionadas seguimos acumulando drift.
3. **Habilitar `pg_stat_statements` + `pgcrypto` + `pg_trgm`** en Render — bajo costo, alto valor.
4. **Activar PgBouncer + RLS** — protege contra leaks y picos de conexiones.
5. **DR drill trimestral** + monitoring de slot lag — la mejor backup es la que ya probaste restaurar.

## Roadmap sugerido por Pack

| Pack | Foco |
| --- | --- |
| 49 | F-001 + F-007, adoptar Alembic, habilitar 3 extensions, PgBouncer |
| 50 | Materialized views + cleanup activo + RLS sobre 5 tablas core |
| 51 | Partitioning de `scans`, `ai_decisions_log`, `staff_audit_log` |
| 52 | Read replica + dashboards Grafana en producción |
| 53 | DW export operativo + CDC LISTEN/NOTIFY mínimo |
| 54+ | Multi-region (si métricas justifican), TimescaleDB re-evaluación |

## Cómo usar este índice

- Para **operar** hoy: empezar por `on-call-playbook.md` + `dba-runbook.md`.
- Para **planificar** el próximo trimestre: `cost-forecast.md` + `schema-2027-vision.md`.
- Para **responder un incidente**: `disaster-playbook.md` + `edge-cases-playbook.md`.
- Para **una migration**: `migration-runbook.md` + `schema-versioning.md`.
- Para un **diagnóstico rápido**: `monitoring-queries.sql`.

## Out-of-scope (no cubierto en Pack 48-H)

- App code changes (subagente D).
- Implementación real de RLS / Alembic / partitioning (sólo specs).
- Configuración real de Grafana, PagerDuty, S3 backups (sólo specs).
- Compliance certification (SOC2, GDPR forms) — diseño preparado, ejecución no.

---

**Sprint cerrado · Pack 48-H · 21 docs + 12 scripts.**
