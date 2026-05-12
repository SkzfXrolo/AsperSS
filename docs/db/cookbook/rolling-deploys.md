# Rolling deploys (Pack 48-H Round 6 · #165)

## Idea

Reemplazar instancias app gradualmente; DB schema debe convivir N versiones.

## Reglas

- N = 2 versiones app coexistiendo durante deploy.
- DB schema cambia **antes** del rollout y debe ser **backward compatible**.
- Drop columns/tablas: pack siguiente.

## Argus

Pack 49 plan asume rolling deploy soportado por Render. Documentar en runbook.

## Referencias

- `docs/db/cookbook/zero-downtime-changes.md`
- `docs/db/render-runbook.md`
