# Ban history history (Pack 48-H Round 6 · #163)

## Modelo

`ban_history` append-only: cada decisión ban/unban genera row.

## Queries útiles

- ¿Está actualmente baneado un jugador?
  ```sql
  SELECT player_uuid, banned_at, unbanned_at
  FROM ban_history
  WHERE player_uuid = $1
  ORDER BY banned_at DESC LIMIT 1;
  ```

## Compliance

- Retención indefinida típica.
- Anonimización post N años si legal permite.

## Argus

Documentar duración exacta retención con legal antes de cualquier cleanup.

## Referencias

- `docs/db/data-modeling/temporal-data.md`
