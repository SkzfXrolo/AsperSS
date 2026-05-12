# Network security (pg_hba, SSL, certs) (Pack 48-H Round 5 · #146)

## pg_hba.conf

Reglas ordenadas: primer match gana.

```text
hostssl all all 0.0.0.0/0 scram-sha-256
```

Evitar `trust` salvo local socket dev.

## SSL modes cliente

| sslmode | Uso |
| --- | --- |
| require | cifra, no verifica cert |
| verify-full | producción ideal |

## Cert rotation

- Dual cert period overlap.
- Alertas expiración <30d.

## Argus

Forzar `sslmode=require` mínimo en `DATABASE_URL` (ver `encryption-strategy.md`).

## Referencias

- `docs/db/render-runbook.md`
