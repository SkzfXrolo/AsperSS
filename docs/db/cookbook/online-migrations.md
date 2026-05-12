# Online migrations (Pack 48-H Round 6 · #165)

## Definición

Migraciones que se aplican **sin downtime** y **sin bloquear** writes/reads de forma perceptible.

## Toolkit

- `CREATE INDEX CONCURRENTLY`.
- `ALTER TABLE ... NOT VALID` + `VALIDATE`.
- Dual-write + backfill + cutover para changes destructivos.
- `pg_repack` para reordenar/compactar (si disponible).

## Reglas

- Una migration online no debe tardar > 30 min total.
- Si tarda más: dividir en pasos.

## Argus

Pack 49 índices + F-001 son ejemplos típicos.

## Referencias

- `docs/db/cookbook/zero-downtime-changes.md`
