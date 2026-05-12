# Versioned rows (Pack 48-H Round 6 · #162)

## Patrón

Cada cambio crea nueva fila con `version` y `is_current` o `valid_from/valid_to`.

```sql
CREATE TABLE company_settings (
  id BIGSERIAL,
  company_id INT NOT NULL,
  version INT NOT NULL,
  settings JSONB NOT NULL,
  valid_from TIMESTAMPTZ NOT NULL,
  valid_to TIMESTAMPTZ,
  PRIMARY KEY (company_id, version)
);
```

## Index recomendado

```sql
CREATE INDEX ON company_settings(company_id) WHERE valid_to IS NULL;
```

## Argus

Aplicable a configuración por compañía / reglas Oracle.

## Referencias

- `docs/db/data-modeling/temporal-data.md`
