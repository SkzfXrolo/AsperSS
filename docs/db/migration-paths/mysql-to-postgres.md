# MySQL → PostgreSQL (Pack 48-H Round 6 · #160)

## Diferencias críticas

| Tema | MySQL | PostgreSQL |
| --- | --- | --- |
| Storage engine | InnoDB / MyISAM | uno solo |
| `AUTO_INCREMENT` | column attribute | `SERIAL` / `IDENTITY` |
| Case sensitivity | depende OS | identifiers case-folded unless quoted |
| Strings | `VARCHAR(N)` mucho usado | `TEXT` preferido |
| Booleans | `TINYINT(1)` | `BOOLEAN` |
| JSON | `JSON` | `JSONB` |
| Group by laxo | permitido | strict salvo PG 9.x mode |
| Default charset | utf8mb4 | UTF-8 nativo |
| ENUM | type real | preferir CHECK / DOMAIN |

## Herramientas

- `pgloader` (canónico).
- AWS DMS para cargas grandes.
- Custom: `mysqldump --compatible=postgresql` + scripts.

## Checklist

- [ ] Mapear tipos.
- [ ] Reescribir queries `BACKTICKS` → comillas dobles.
- [ ] Adaptar `ON DUPLICATE KEY UPDATE` → `ON CONFLICT`.
- [ ] Funciones agregadas (e.g. `GROUP_CONCAT` → `string_agg`).
- [ ] Tests integración.

## Argus

Si en algún futuro hay integraciones con MySQL externos, usar FDW (`fdw.md`) en vez de migrar todo.

## Referencias

- pgloader docs
