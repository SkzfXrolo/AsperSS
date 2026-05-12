# Trigger performance considerations (Pack 48-H Round 5 · #144)

## Coste

Cada `INSERT/UPDATE` ejecuta triggers adicionales → CPU + locks en tablas tocadas.

## Reglas

- Mantener triggers **O(1)** por fila; evitar subqueries grandes.
- Evitar cascadas profundas trigger→trigger.
- `WHEN` clause para filtrar invocaciones:

```sql
CREATE TRIGGER t1 BEFORE UPDATE ON scans
FOR EACH ROW WHEN (OLD.risk_score IS DISTINCT FROM NEW.risk_score)
EXECUTE FUNCTION argus_touch_updated_at();
```

## Medición

- `EXPLAIN ANALYZE` con y sin trigger (deshabilitar temporalmente en staging).
- `pg_stat_user_functions` para tiempo en funciones trigger.

## Argus

Triggers NOTIFY: riesgo thundering herd si alta frecuencia — batch en app o debounce externo.

## Referencias

- `docs/db/edge-cases-playbook.md`
