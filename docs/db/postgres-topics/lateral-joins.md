# LATERAL joins (Pack 48-H Round 5 · #140)

## Idea

`LATERAL` permite que una subconsulta en `FROM` referencie columnas de tablas anteriores **por fila**.

## Patrón top-N por grupo

```sql
SELECT c.id, s.*
FROM companies c
CROSS JOIN LATERAL (
  SELECT * FROM scans s
  WHERE s.company_id = c.id
  ORDER BY s.created_at DESC
  LIMIT 5
) s;
```

## vs window functions

- `LATERAL` + `LIMIT` puede ser más legible para top-N pequeño.
- Window `ROW_NUMBER()` a veces más eficiente según plan.

## Argus

- Últimas 3 decisiones Oracle por jugador en una query panel.

## Precaución

- `CROSS JOIN LATERAL` sin `LIMIT` interno puede explotar filas.

## Referencias

- `docs/db/window-functions.md`
