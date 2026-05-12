# SECURITY DEFINER pattern (Pack 48-H Round 5 · #143)

## Qué hace

`SECURITY DEFINER` ejecuta la función con privilegios del **owner** de la función, no del caller.

## Riesgos

- Escalación de privilegios si `search_path` permite hijacking (`CREATE FUNCTION lower(text)` en schema malicioso).
- Exponer datos cross-tenant si no se filtra `company_id` explícitamente.

## Plantilla segura

```sql
CREATE SCHEMA IF NOT EXISTS argus_priv;
CREATE OR REPLACE FUNCTION argus_priv.do_sensitive(...)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, argus_priv
AS $$ ... $$;
REVOKE ALL ON FUNCTION argus_priv.do_sensitive(...) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION argus_priv.do_sensitive(...) TO app_role;
```

## Cuándo usar

- Centralizar chequeos RLS bypass controlado (maintenance).
- Rotación de secrets vía extension no disponible.

## Argus

Evitar DEFINER salvo caso claro; preferir RLS + roles mínimos.

## Referencias

- `docs/db/security-advanced/privilege-management.md`
