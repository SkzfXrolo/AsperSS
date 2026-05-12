# Onboarding de tests

## Primer test rápido

1. Crear archivo en `tests/`.
2. Reusar fixtures de `tests/conftest.py` y `tests/_lib/fixtures.py`.
3. Ejecutar `python -m pytest <archivo> -q`.

## Utilidades recomendadas

- `tests/_lib/factories.py` para generar data.
- `tests/_lib/asserts.py` para aserciones comunes.
- Markers: `perf`, `e2e`, `load`, `smoke`, `contract`, `chaos`.
