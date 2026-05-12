# Contract tests (Schemathesis)

## Ejecutar

```bash
python -m pip install -r tests/requirements-test.txt
python -m pytest -m contract tests/contract -q
```

## Extender OpenAPI

1. Agregar endpoint en `tests/contract/openapi.yaml`.
2. Definir requestBody y respuestas esperadas.
3. Correr tests de contrato y ajustar status codes aceptados.
