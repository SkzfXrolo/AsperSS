# Bug backlog testing

- `Pack49-BUG-NaNInf`: `argus_ai_features.extract_features` no sanea completamente NaN/Inf/negativos en evidencia rara.
  - Evidencia: `tests/test_features_extraction.py::test_no_nan_or_inf_with_weird_evidence`
  - Estado: abierto
  - Owner sugerido: D
