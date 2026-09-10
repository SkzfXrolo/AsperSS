# Argus Panel — variables de entorno para el deploy

Generado del código (`grep os.environ` en `web_app/*.py`). El panel **arranca
solo con el bloque MÍNIMO**; el resto son feature-flags (si falta, la feature
queda desactivada, no rompe el boot).

Host: servicio de procesos largos (Railway / Render / Fly). **No Vercel**
(gunicorn + SocketIO + bot de Discord).

Arranque: `gunicorn --config gunicorn_config.py app:app`
Healthcheck: `GET /healthz` → `{"ok":true,...}` (no toca BD)
Python: **3.12.7** (`runtime.txt`; en Render usar `PYTHON_VERSION=3.12.7`).
No subir a 3.13+ sin actualizar `psycopg2-binary` y `cryptography` a la vez.

---

## MÍNIMO (sin esto el panel no sirve)

| Variable | Qué es | Nota |
|---|---|---|
| `DATABASE_URL` | Postgres (`postgresql://user:pass@host:5432/db`) | Railway lo inyecta como `${{Postgres.DATABASE_URL}}`. Render con `fromDatabase`. Si falta → cae a SQLite efímero (se pierde al reiniciar). |
| `SECRET_KEY` | Firma de sesiones Flask | Valor aleatorio largo. Si no se setea usa un placeholder inseguro. Render: `generateValue: true`. |

## RECOMENDADO en producción

| Variable | Default si falta | Para qué |
|---|---|---|
| `FLASK_ENV` | — | `production` |
| `PUBLIC_BASE_URL` | se deriva del host | URL pública del panel (links en emails/Discord, API del scanner). Ej. `https://aspers-web-production.up.railway.app` |
| `SUPER_ADMIN_USER` / `SUPER_ADMIN_PASS` | — | Bootstrap del primer superadmin. Se puede quitar después del primer login. |
| `ARGUS_PANEL_OWNER_USERNAMES` | — | Coma-separado; usuarios con vista de owner del panel v2. |

## Base de datos alternativa (si NO usás `DATABASE_URL`)

`POSTGRES_HOST` `POSTGRES_PORT` `POSTGRES_USER` `POSTGRES_PASSWORD` `POSTGRES_DATABASE`
— o MySQL: `MYSQL_HOST` `MYSQL_PORT` `MYSQL_USER` `MYSQL_PASSWORD` `MYSQL_DATABASE` `MYSQL_SSL_CA`

## IA / oráculo (opcional — si falta, esa feature se apaga)

| Variable | Proveedor |
|---|---|
| `GEMINI_API_KEY` (+ `ARGUS_GEMINI_MODEL`) | Google Gemini |
| `ANTHROPIC_API_KEY` | Claude |
| `GROQ_API_KEY` | Groq |
| `OPENAI_API_KEY` (+ `OPENAI_MODEL`) | OpenAI |
| `ARGUS_CORE_PROVIDER` | cuál usar por defecto |
| `ABUSEIPDB_API_KEY` | reputación de IPs |

## Bot de Discord (opcional)

`DISCORD_TOKEN` `DISCORD_GUILD` `DISCORD_CHANNEL` `DISCORD_STAFF_ROLE`
`DISCORD_PUBLIC_KEY` `DISCORD_DEPLOY_WEBHOOK` `DISCORD_AI_HEALTH_WEBHOOK`

## Notificaciones push (opcional)

`VAPID_PUBLIC_KEY` `VAPID_PRIVATE_KEY` `VAPID_EMAIL`

## Email / SMTP (opcional)

`SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASS` `SMTP_FROM`

## Telegram (opcional)

`TELEGRAM_BOT_TOKEN` `TELEGRAM_CHAT_ID`

## Cache / cola (opcional)

`REDIS_URL` — si falta, se usa cache en memoria del proceso.

## Otras (opcionales / internas)

`SOCKETIO_CORS_ALLOWED_ORIGINS` · `LOG_FORMAT` · `ARGUS_PUBLIC_BANNER` ·
`ARGUS_LICENSE_MAX_AGE` · `ARGUS_INTERNAL_REVIEW_SECRET` · `ARGUS_ADMIN_JWT_SECRET` ·
`ARGUS_BOOTSTRAP_USER` / `ARGUS_BOOTSTRAP_TOKEN` / `ARGUS_BOOTSTRAP_EMAIL`

## NO setear en producción

`ARGUS_FORCE_SQLITE` · `ARGUS_DB_PATH` · `ARGUS_LOCAL_DEV` · `FLASK_DEBUG` ·
`LOCAL_DEV_SECRET` — son solo para desarrollo local.

---

## Migrar datos entre hosts

```bash
# origen (Render/Railway viejo): copiar External Database URL del dashboard
pg_dump "postgresql://..." -Fc -f aspers.dump
# destino:
pg_restore --no-owner -d "$DATABASE_URL" aspers.dump
```
