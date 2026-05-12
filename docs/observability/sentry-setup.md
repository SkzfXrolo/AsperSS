# Sentry Setup (Python + JS) — Pack48-G

## Backend Python (Flask)

1. Instalar:
```bash
pip install sentry-sdk[flask]
```
2. Inicializar en bootstrap:
```python
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1,
    environment=os.getenv("ENV", "prod"),
    release=os.getenv("RELEASE_SHA", "dev"),
)
```

## Frontend JS

1. Instalar:
```bash
npm i @sentry/browser @sentry/tracing
```
2. Inicializar:
```js
Sentry.init({
  dsn: window.SENTRY_DSN,
  tracesSampleRate: 0.1,
  environment: window.APP_ENV || "prod",
  release: window.APP_RELEASE || "dev",
});
```

## Buenas prácticas

- Redactar PII (`user_id` hash, no emails en claro si no es necesario).
- Capturar errores no manejados + breadcrumbs de acciones clave.
- Alertas por incremento de error rate en 5m/30m.
