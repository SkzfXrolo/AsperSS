# Soft-delete patterns (Pack 48-H Round 6 · #157)

## Variantes

| Variante | Descripción |
| --- | --- |
| `deleted_at TIMESTAMPTZ NULL` | popular |
| `is_deleted BOOLEAN` | sin marca temporal |
| Archive table | mover fila a `_archive` |

## Pros

- Recovery sencillo.
- Audit natural.

## Cons

- Olvido de filtro → leak de filas borradas.
- Tabla crece indefinidamente.

## Mitigaciones

- **Vista** `active_table` con filtro built-in.
- Partial indexes `WHERE deleted_at IS NULL`.
- RLS policy filtra deleted.

## Argus

Política: soft-delete + cleanup mensual (mover a `_archive` o `DELETE` post legal).

## Referencias

- `docs/db/anti-patterns.md`
