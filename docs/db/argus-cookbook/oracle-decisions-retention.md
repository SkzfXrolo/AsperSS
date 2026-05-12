# Oracle decisions retention (Pack 48-H Round 6 · #163)

## Política propuesta

- 6 meses hot en `ai_decisions_log`.
- 12 meses anonimizado en cold storage.
- Métricas agregadas indefinidas (MV).

## Anonimización

- Hash de `player_uuid`.
- Drop chat content tras 6m si compliance lo permite.

## Re-entrenamiento

Si dataset training necesita > 6m: versionar snapshot (`ml-data/training-data-versioning.md`).

## Referencias

- `docs/db/argus-scenarios/oracle-decisions-archival.md`
