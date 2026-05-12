# DQ checks catalog (Pack 48-H Round 6 · #158)

Lista representativa; detalle SQL en `scripts/db/data-quality.sql` y `integrity-checks.sql`.

| ID | Dimensión | Tabla | Check |
| --- | --- | --- | --- |
| DQ-001 | completeness | scans | `company_id NOT NULL` (pendiente F-001) |
| DQ-002 | uniqueness | ai_player_profiles | `(company_id, player_uuid)` único |
| DQ-003 | validity | scans | `risk_score BETWEEN 0 AND 100` |
| DQ-004 | timeliness | scans | freshness < 5 min |
| DQ-005 | consistency | scans→companies | FK válida (LEFT JOIN IS NULL) |
| DQ-006 | validity | ai_decisions_log | `verdict IN ('BAN','WARN','ALLOW')` |
| DQ-007 | accuracy | violations | `severity IN (1..5)` |
| DQ-008 | uniqueness | users | email único activo |
| DQ-009 | consistency | ban_history | `unbanned_at IS NULL OR unbanned_at >= banned_at` |
| DQ-010 | completeness | staff_audit_log | `actor_user_id NOT NULL` cuando aplica |

## Referencias

- `scripts/db/data-quality.sql`
