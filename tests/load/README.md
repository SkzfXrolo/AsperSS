# Load testing (Locust)

## Instalar deps de carga

```bash
python -m pip install -r tests/requirements-load.txt
```

## Correr contra staging

```bash
locust -f tests/load/locustfile.py --host https://staging.example.com
```

Abrir UI de Locust y configurar usuarios/spawn rate según el entorno.
