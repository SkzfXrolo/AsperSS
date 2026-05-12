# When to use triggers (Pack 48-H Round 5 · #144)

## Buen uso

- Auditoría append-only (`argus_audit_row`).
- `updated_at` automático (`argus_touch_updated_at`).
- CDC liviano `NOTIFY` con throttling externo.

## Mal uso

- Lógica de negocio compleja difícil de testear.
- Llamadas HTTP desde trigger (latencia, fiabilidad).
- Duplicar validaciones ya hechas en app sin valor.

## Argus posición

Alineado con `stored-procedures-vs-app.md`: triggers mínimos, audit/CDC nada más salvo caso excepcional documentado.

## Referencias

- `docs/db/triggers-deep/audit-triggers.md`
