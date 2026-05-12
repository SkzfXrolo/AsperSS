# Schema diff tools (Pack 48-H Round 6 · #164)

| Tool | Notas |
| --- | --- |
| `pg_dump --schema-only` + `diff` | low-tech, sirve |
| `migra` | genera SQL diff Python |
| `apgdiff` | Java, maduro |
| `schemaspy` | docs visuales |
| `tbls` | docs Go, integra CI |

## Argus

Empezar con `migra` o script propio (`schema-drift-check.py` ya hace ~esto).

## Referencias

- `scripts/db/schema-drift-check.py`
