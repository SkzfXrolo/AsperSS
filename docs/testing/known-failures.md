# Known failures

## `tests/test_oracle_phrases.py::test_each_bucket_has_at_least_50_non_empty_phrases`
- Motivo: `argus_ai_oracle.PHRASES` tenía ~30 frases por bucket en builds previos.

## `tests/test_features_extraction.py::test_no_nan_or_inf_with_weird_evidence`
- Motivo: `math.log1p(rep)` con `reports_in_chat` negativo.

## `tests/test_assistant_intent_classifier.py` (2 casos históricos)
- Motivo: regex de `classify_intent` incompleta para español coloquial.

## Warning de import en Windows (`cp1252`)
- Motivo: logs con unicode en `init_db_async` pueden disparar `UnicodeEncodeError`.
