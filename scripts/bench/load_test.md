# Load Testing Setup (Locust) — Pack48-G

## Objetivo

Simular tráfico realista del web app:
- login
- browse panel/scans
- submit scan
- oracle evaluate

## Ejecutar

1. Instalar:
```bash
pip install locust
```

2. Levantar:
```bash
locust -f scripts/bench/locustfile.py --host=https://asperss.onrender.com
```

3. Abrir UI:
- [http://localhost:8089](http://localhost:8089)

## Escenarios sugeridos

- `PanelBrowseUser` (peso 50)
- `ApiScansUser` (peso 30)
- `OracleEvalUser` (peso 15)
- `ScanSubmitUser` (peso 5)

## Targets

- p95 < 400ms para endpoints de lectura.
- p99 < 800ms para endpoints pesados.
- error rate < 1%.
