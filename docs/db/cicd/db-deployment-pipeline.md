# DB deployment pipeline (Pack 48-H Round 6 · #164)

## Etapas

```
PR -> CI (lint, tests) -> Merge -> Staging deploy -> Smoke -> Manual gate -> Prod deploy -> Monitor
```

## Detalle staging

- Espejo schema prod.
- Datos sintéticos (`synthetic-data-generator.py`).
- Run migration + tests.

## Detalle prod

- `alembic upgrade head` antes de release app.
- Si falla → app no boot nueva versión → previous release sigue activo.

## Roles

| Rol | Responsabilidad |
| --- | --- |
| Dev | escribir migration + tests |
| Reviewer | DBA aprueba |
| CI | gating automático |
| Release manager | ventana + comunicación |

## Argus

Pack 49 mete pipeline mínimo; refinar Pack 50+.

## Referencias

- `docs/db/migration-tooling-deep.md`
