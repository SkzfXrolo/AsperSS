# Privilege management (Pack 48-H Round 5 · #146)

## Roles

| Rol | Privilegios |
| --- | --- |
| `app_rw` | DML tablas app |
| `app_ro` | SELECT |
| `migrator` | DDL migrations CI |
| `reporter` | SELECT + `SET ROLE` opcional |

## Default privileges

```sql
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
```

## REVOKE PUBLIC

```sql
REVOKE ALL ON SCHEMA public FROM PUBLIC;
```

## Search path

Fijar `search_path=public` en roles app para evitar search_path attacks con DEFINER.

## Referencias

- `docs/db/security-hardening.md`
