# Panel local — réplica de asperss.onrender.com

Entorno para probar **cambios visuales**, **tokens**, **panel staff**, etc. en tu PC, usando la **misma base de datos** que Render (opcional pero recomendado para ver datos reales).

## Qué sí y qué no hace

| Sí | No |
|----|-----|
| Misma app Flask que en Render (`web_app/app.py`) | Los cambios de código **no** aparecen solos en Render |
| Misma PostgreSQL si configuras `DATABASE_URL` | No sustituye el deploy: hace falta `git push` → auto-deploy |
| Solo accesible desde tu PC (`127.0.0.1`) | No uses `0.0.0.0` en local si no quieres exponer la red LAN |
| Hot-reload con `FLASK_DEBUG=1` | Editar en local **no** modifica producción hasta hacer push |

## Setup (una vez)

### 1. Python y dependencias

```powershell
cd aspersprojectsSS-main
python -m venv .venv
.\.venv\Scripts\activate
pip install -r web_app\requirements.txt
```

### 2. Variables de entorno

```powershell
copy web_app\.env.local.example web_app\.env.local
```

En [Render Dashboard](https://dashboard.render.com) → servicio **aspers-app** → **Environment** (o base **aspers-db** → **Connect**):

- Copia **External Database URL** → pégala en `DATABASE_URL` dentro de `.env.local`.

No subas `.env.local` a git (ya está en `.gitignore`).

### 3. Arrancar

**Windows:**

```
BAT\INICIAR_PANEL_LOCAL.bat
```

**PowerShell:**

```powershell
.\scripts\dev\start-local-panel.ps1
```

Abre: **http://127.0.0.1:8080/panel**  
Login: la misma cuenta que en producción (misma BD).

## Seguridad (solo tú)

Con `ARGUS_LOCAL_DEV=1` (por defecto en `.env.local.example`):

- El servidor escucha solo en **127.0.0.1** (no en la red Wi‑Fi).
- Peticiones que no vengan de localhost reciben **403**.
- Opcional: define `LOCAL_DEV_SECRET=...` en `.env.local` y abre el panel con:
  - `http://127.0.0.1:8080/panel?_local_dev=TU_SECRETO`, o
  - Header `X-Local-Dev-Secret: TU_SECRETO` (útil para scripts).

## Flujo de trabajo recomendado

1. **UI / CSS / JS del panel** → cambias en local → recargas el navegador → cuando esté bien → `git push` → Render despliega.
2. **Scanner `.exe`** → cambias `source/` → bump versión → PyInstaller → commit con el exe → push.
3. **Datos de prueba** → con BD de Render tenés scans/tokens reales; ten cuidado al crear tokens o cambiar veredictos (afecta producción).

## Alternativa: BD local aislada

Si no quieres tocar producción:

```powershell
cd docker
copy .env.example .env
docker compose up -d postgres redis web
```

Eso usa Postgres **vacío** en Docker, no la de Render.

## Diferencia con scripts viejos

| Script | Uso |
|--------|-----|
| `INICIAR_PANEL_LOCAL.bat` | **Recomendado** — réplica Render (un solo proceso, puerto 8080) |
| `INICIAR_SISTEMA_COMPLETO.bat` | Legacy — API en :5000 + web en :8080 |
| `INICIAR_CON_CLOUDFLARE.bat` | Expone local a internet (no recomendado para panel privado) |

## Troubleshooting

- **SQLite en logs** → falta `DATABASE_URL` en `.env.local`.
- **401 / sin datos** → sesión distinta; inicia sesión de nuevo en local.
- **No conecta a Postgres** → en Render, activa acceso externo a la BD y usa la URL **External**, no la internal-only.
- **Puerto ocupado** → cambia `PORT=8081` en `.env.local` y `API_URL=http://127.0.0.1:8081`.
