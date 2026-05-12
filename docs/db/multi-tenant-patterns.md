# Multi-tenant patterns (Pack 48-H Round 4 · #116)

## El espectro

```
   Shared DB / shared schema       Shared DB / schema-per-tenant     DB-per-tenant
   ───────────────────────         ────────────────────────────       ────────────
   un PG, una tabla "scans"         un PG, schemas s_001, s_002…       un PG por cliente
   con tenant_id en cada fila        cada uno con su "scans"            o cluster por cliente
   (Argus actual)                    (PG max ~10k schemas práctico)     (no scalable >100)
```

| Dimensión | Shared/shared | Shared/schemas | DB-per-tenant |
| --- | --- | --- | --- |
| Isolation lógica | bajo (depende de app/RLS) | medio (search_path / GRANT) | alto |
| Isolation perf | bajo (noisy neighbor en CPU/IO) | bajo | alto |
| Costo per tenant | bajo | medio | alto |
| Complejidad ops | baja | media | alta (1 DB × N) |
| Migrations | una migration global | una × schema | una × DB |
| Cross-tenant analytics | trivial (un GROUP BY) | UNION ALL N schemas | hard (FDW o ETL a DW) |
| Compliance residency (per region) | difícil | medio | nativo |
| Backups individuales | difícil | medio | trivial |
| Onboarding cost | trivial (INSERT en companies) | crear schema | provisionar DB |
| Soft delete cliente | UPDATE flag | DROP SCHEMA | DROP DATABASE |

## Estado actual de Argus

**Shared/shared** (un PG, columna `company_id` per fila). Es lo más común en SaaS B2B en etapas tempranas. Pros:

- 1 schema, 1 set de migrations, 1 backup.
- Costos lineales con uso, no con # clientes.
- Analytics cross-tenant: queries normales.

Riesgos vigentes:

- F-001: hoy `scans` no tiene `company_id` → leaks lógicas potenciales por bug app.
- Tenant ruidoso puede consumir todo (no aislamiento de recursos).
- Compliance: si llega cliente con cláusula "mis datos en EU separados", no la cumplimos.

## Cuándo cada uno

| Situación | Recomendado |
| --- | --- |
| Hasta 1k clientes B2B SMB | Shared/shared + RLS (Argus hoy) |
| 1k-10k clientes, mismo region | Shared/shared con sharding por `company_id` |
| Cliente enterprise con compliance | DB-per-tenant para ESE cliente (híbrido) |
| GDPR residency EU | DB en EU para esos clientes |
| Pruebas A/B aisladas | schema-per-tenant temporal |

## Patrón híbrido (recomendado mediano plazo)

```
PG-shared-us-east  ← 95% clientes (SMB, free, pro)
PG-shared-eu       ← clientes EU (data residency)
PG-dedicated-X     ← cliente enterprise X (SLA dedicado)
```

App enruta por `companies.shard_key`.

## RLS (Row Level Security) en shared/shared

Cubierto en `security-hardening.md` (#108). Resumen:

```sql
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
CREATE POLICY scans_tenant ON scans
    USING (company_id = current_setting('app.company_id', true)::int);
```

App: `SET LOCAL app.company_id = N` al inicio de cada request.

**Sin RLS**: app es la única defensa → un `WHERE` olvidado = leak.
**Con RLS**: PG enforce kernel-side. Aún hay que cuidar de no usar conexión con rol `bypass_rls`.

## Schema-per-tenant — cuándo merece la pena

- Si data per tenant es **grande** (>10GB cada uno).
- Si cada cliente tiene **schema customizado** (columnas extra, joins propios).
- Si onboarding incluye **carga de seed data masiva** (mejor `pg_dump` skeleton + restore).

Limitaciones:

- PG: 10k schemas funcionan pero el catalog crece (`pg_class` con millones).
- Migrations: hay que iterar todos los schemas (lock contention, ventanas largas).
- Backups: pg_dump por schema funciona, pero archive completo no diferencia.

## DB-per-tenant — sólo casos extremos

Operación se vuelve compleja:

- Backups N veces.
- Monitoring N targets.
- Migrations: orchestrator (Liquibase, Flyway multi-target).
- Provisioning automatizado (Terraform).

Solo justificado para clientes **enterprise** con SLA dedicado o compliance estricto.

## Recomendación Argus

**Quedarse en shared/shared** y reforzarlo:

1. **F-001**: agregar `company_id` faltante (subagente D).
2. **RLS** sobre las 12 tablas core (`security-hardening.md`).
3. **Sharding por `company_id`** preparado pero no activado (`sharding-design.md`).
4. **Resource isolation** capa app (rate limiting per company).
5. **Plan B compliance**: cuando llegue cliente que pida residency, abrir 2do cluster en EU; app enruta por `company.region_id`.

## Métricas de "ruido cross-tenant"

```sql
-- queries por tenant en pg_stat_statements (requiere agregar tenant a app_name)
SELECT
    substring(application_name from 'cid=(\d+)') AS company_id,
    sum(total_exec_time)  AS total_ms,
    sum(calls)            AS n_calls
FROM pg_stat_statements
WHERE application_name LIKE 'web/cid=%'
GROUP BY 1
ORDER BY total_ms DESC LIMIT 20;
```

Setear `application_name` con `cid=<company_id>` en cada conexión para tracear.

## Anti-patterns

1. ❌ Hardcodear UNION queries que asumen "todos los tenants" → leak.
2. ❌ Olvidar `WHERE company_id = ?` (peor con bind params).
3. ❌ Permitir un tenant que escriba en tabla global sin scoping.
4. ❌ ID de tenant en URL pero no en query (URL puede ser cambiada por user).

## Checks (ver scripts/db/tenant-isolation-checks.sql)

- "scans en empresa A con scan_token de empresa B"
- "ai_decision_log con company_id distinto a scan.company_id"
- etc. (15 checks, Round 2 entregables).
