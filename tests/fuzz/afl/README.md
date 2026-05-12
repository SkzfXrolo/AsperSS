# AFL-like fuzz target

Target: `tests/fuzz/afl/oracle_target.py`

## Ejemplo con python-afl

```bash
python -m pip install python-afl
bash scripts/test/run-afl-fuzz.sh
```

Input seeds sugeridos: JSONs simples con `violations`.
