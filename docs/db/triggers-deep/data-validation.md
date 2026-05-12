# Validation triggers (Pack 48-H Round 5 · #144)

## Patrón BEFORE INSERT/UPDATE

```sql
CREATE FUNCTION argus_validate_scan() RETURNS trigger AS $$
BEGIN
  IF NEW.risk_score IS NOT NULL AND (NEW.risk_score < 0 OR NEW.risk_score > 100) THEN
    RAISE EXCEPTION 'risk_score out of range';
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
```

## Pros

- Garantía fuerte incluso si app buguea.

## Contras

- Duplicación con CHECK constraints; preferir CHECK cuando basta (más visible en schema).

## Argus

Usar CHECK + tests; triggers sólo cuando reglas cross-column complejas no expresables en CHECK simple.

## Referencias

- `docs/db/triggers-deep/perf-impact.md`
