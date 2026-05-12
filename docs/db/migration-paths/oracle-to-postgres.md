# Oracle → PostgreSQL (genérico) (Pack 48-H Round 6 · #160)

## Diferencias clave

| Tema | Oracle | PG |
| --- | --- | --- |
| Types | `NUMBER`, `VARCHAR2` | `numeric`, `text` |
| Sequences | `seq.nextval` | `nextval('seq')` |
| Empty string == NULL | sí | NO |
| PL/SQL | similar a PL/pgSQL pero distinto | conversiones manuales |
| Hierarchical `CONNECT BY` | propio | `WITH RECURSIVE` |
| Materialized view refresh | rico | más simple |
| Packages | sí | schemas + funciones |

## Herramientas

- **ora2pg**: estándar.
- **AWS SCT** + DMS.

## Argus

No aplica directo; valor de referencia si alguna integración enterprise lo requiere.

## Referencias

- ora2pg docs
