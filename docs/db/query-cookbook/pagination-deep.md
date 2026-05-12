# Pagination deep (offset vs cursor vs keyset) (Pack 48-H Round 6 · #156)

## OFFSET / LIMIT

```sql
SELECT * FROM scans ORDER BY created_at DESC LIMIT 50 OFFSET 10000;
```

- Simple, **degrada** linealmente con OFFSET.
- Inestable si nuevos rows insertados entre páginas.

## Keyset (seek pagination)

```sql
SELECT * FROM scans
WHERE (created_at, id) < ($cursor_ts, $cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT 50;
```

- O(log n) por página con índice adecuado.
- Estable.

## Cursor server-side

`DECLARE cur CURSOR FOR ...` + `FETCH 50`. Útil scripting, no APIs HTTP (stateful).

## Argus

- Panel scans: keyset por `(created_at DESC, id DESC)` con índice covering.
- Reports CSV: server cursor para streams largos.

## Pitfalls

- Mezclar OFFSET en background jobs grandes → CPU desperdiciado.

## Referencias

- `docs/db/index-management/covering-indexes.md`
