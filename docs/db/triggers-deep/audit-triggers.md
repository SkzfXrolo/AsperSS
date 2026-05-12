# Audit trigger patterns (Pack 48-H Round 5 · #144)

## Patrón row-level

```sql
CREATE FUNCTION argus_audit_row() RETURNS trigger AS $$
BEGIN
  INSERT INTO staff_audit_log(table_name, op, row_pk, old_row, new_row, changed_at)
  VALUES (TG_TABLE_NAME, TG_OP, to_jsonb(NEW.*), to_jsonb(OLD.*), to_jsonb(NEW.*), now());
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
```

## Consideraciones PII

- `to_jsonb(NEW.*)` puede incluir PII: clasificar `data-classification.md`.
- Tamaño WAL: auditoría de tablas hot puede ser costosa → async outbox o sampling.

## Alternativas

- `pgaudit` a nivel servidor (si disponible).
- CDC a SIEM.

## Referencias

- `scripts/db/functions/triggers.sql`
