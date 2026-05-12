# Audit log partitioning (Pack 48-H Round 5 · #147)

## Tabla

`staff_audit_log` — crecimiento moderado pero compliance-sensitive.

## Diseño

- Partición RANGE trimestral por `created_at` (ver `partitioning-design.md` Round 3).
- Índices `(company_id, created_at DESC)` por partition attach.

## Queries típicas

- Staff review últimos 7d por `company_id` → partition pruning efectivo.

## Retención

- `DROP PARTITION` tras ventana legal aprobada.

## Referencias

- `scripts/db/partition-migration.sql`
