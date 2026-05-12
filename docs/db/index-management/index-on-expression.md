# Index on expression (Pack 48-H Round 6 · #155)

## Definición

Índice sobre una **expresión** en vez de columna pura:

```sql
CREATE INDEX idx_users_email_lower ON users ((lower(email)));
```

## Reglas

- La query debe usar **exactamente** la misma expresión: `WHERE lower(email) = 'a@b.com'`.
- Función debe ser `IMMUTABLE` (sin `now()`, `random()`).

## Casos Argus

- `lower(username)` para búsquedas case-insensitive.
- `date_trunc('day', created_at)` SOLO si no podés reescribir como range.

## Antipatrones

- Crear expression index para "asegurar" que algo se usa: medir primero.

## Referencias

- `docs/db/anti-patterns.md`
