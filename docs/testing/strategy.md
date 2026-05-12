# Estrategia de testing Argus

## Pirámide

1. **Unit + property** (base más ancha).
2. **Integration** (endpoints y flujos de backend).
3. **Contract** (OpenAPI/Schemathesis).
4. **E2E + a11y + smoke** (menos cantidad, más costo).
5. **Perf/load/mutation** (regresión continua semanal o bajo demanda).

## Targets

- Cobertura AI (`argus_ai_*`): >= 80%.
- Mutation score: >= 70%.
- Perf regressions: <= +20% sobre baseline.
