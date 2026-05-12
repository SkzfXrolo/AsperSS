# Known failures (Pack48-E)

## `tests/test_oracle_phrases.py::test_each_bucket_has_at_least_50_non_empty_phrases`
- **Motivo**: `argus_ai_oracle.PHRASES` hoy trae ~30 frases por bucket (`clean/watch/ss/kick/ban`), no 50+.
- **Impacto**: no cumple el criterio de robustez de variación lingüística solicitado por sprint.
- **Fix en producción**: ampliar cada bucket a >= 50 frases.

## `tests/test_features_extraction.py::test_no_nan_or_inf_with_weird_evidence`
- **Motivo**: `argus_ai_features.extract_features()` hace `math.log1p(rep)` sin clamp y crashea con `reports_in_chat` negativo (`ValueError: math domain error`).
- **Impacto**: evidencia corrupta/atípica puede romper extracción de features.
- **Fix en producción**: clampear `rep = max(0.0, rep)` antes de `log1p`.

## `tests/test_assistant_intent_classifier.py` (2 casos)
- **Motivo**: `classify_intent()` no reconoce frases comunes como `que tal` (greeting) ni `porque baneaste a X` (explain_decision) por cobertura limitada de regex.
- **Impacto**: UX del asistente pierde intents frecuentes en español coloquial.
- **Fix en producción**: ampliar `INTENT_PATTERNS` para variantes `que tal`, `porque ...`, y verbos sin acento.
