# Vertical sharding (Pack 48-H Round 6 · #153)

## Concepto

Separar **tablas o grupos de tablas** por **dominio** en **distintos servidores**.

Ejemplo Argus hipotético:

- DB `auth` → `users`, `sessions`, `api_keys`.
- DB `scans` → `scans`, `violations`, `ai_decisions_log`.
- DB `audit` → `staff_audit_log`, `ddl_log`.

## Pros

- Aislar carga (audit no compite con scans).
- Backup/replication policies por dominio.
- Tier distinto por necesidad.

## Cons

- JOINs cross-DB difíciles (FDW o app composition).
- Transacciones distribuidas raras / no triviales.
- Más superficie ops (3 DBs vs 1).

## Argus

Aplicaría si **un dominio** crece desbalanceado (ej. `scans` empuja CPU al techo).

## Referencias

- `docs/db/sharding/horizontal-sharding.md`
- `docs/db/argus-sharding-when.md`
