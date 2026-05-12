# Fuzzing Strategy

## Objetivo

Detectar crashes, invariantes rotas y edge-cases en superficies de entrada no confiables.

## Harness incluidos

- `scripts/security/fuzz/oracle_fuzzer.py`
- `scripts/security/fuzz/assistant_fuzzer.py`
- `scripts/security/fuzz/scanner_input_fuzzer.py`

## Cuándo correr

- en PRs que toquen IA/parser/auth endpoints,
- nightly (CI programada),
- antes de release.

## Criterio de fallo

- excepción no manejada,
- timeout excesivo repetido,
- salida no serializable o incoherente,
- memory spike no esperada.

## Comando sugerido

```bash
python scripts/security/fuzz/oracle_fuzzer.py
python scripts/security/fuzz/assistant_fuzzer.py
python scripts/security/fuzz/scanner_input_fuzzer.py
```
