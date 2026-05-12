# Polymorphic association (Pack 48-H Round 6 · #157)

## Anti-patrón

```text
target_id BIGINT, target_type TEXT
```

Sin FK formal.

## Alternativas

| Alternativa | Descripción |
| --- | --- |
| Tabla por tipo + super-tabla | normalización clara |
| Multi-column FK nullable | una columna por tipo (`scan_id`, `player_id`, ...) |
| `CHECK` + tabla discriminator validado | hibrido |

## Argus

- `staff_audit_log.target_type/target_id`: tolerable con tests integridad estrictos.
- Para nuevas tablas: preferir FK explícita.

## Referencias

- `docs/db/anti-patterns.md`
