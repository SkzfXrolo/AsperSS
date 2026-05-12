# Audit log patterns (Pack 48-H Round 6 · #157)

## Patrones

| Patrón | Descripción |
| --- | --- |
| Row triggers → `*_audit_log` | clásico |
| Single `audit_log` polymorphic | central, JSONB |
| Outbox + CDC | escalable |
| `pgaudit` (si disponible) | server-side |

## Esquema central propuesto

| col | tipo |
| --- | --- |
| `id` | BIGSERIAL PK |
| `created_at` | TIMESTAMPTZ |
| `actor_user_id` | INT |
| `target_type` | TEXT |
| `target_id` | TEXT |
| `op` | TEXT (`insert`/`update`/`delete`/`login`) |
| `before` | JSONB NULL |
| `after` | JSONB NULL |
| `request_id` | TEXT |
| `ip` | TEXT (anonimizado) |

## Argus

`staff_audit_log` existente alineable a este esquema durante refactor Pack 50+.

## Referencias

- `docs/db/triggers-deep/audit-triggers.md`
