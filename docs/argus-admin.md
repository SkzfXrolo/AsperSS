# ArgusAdmin — Control Imperial

Producto **activo**: SuperAdmin de escritorio con candado por voz + API en Render.

Código: [`argus-admin/`](../argus-admin/)

## Inicio rápido

```powershell
cd argus-admin
pip install -r requirements.txt
python run_argus_admin.py
```

O: `BAT\INICIAR_ARGUS_ADMIN.bat`

## Deploy necesario (si ves 404 al grabar voz)

Si ArgusAdmin dice **«respuesta no es JSON (HTTP 404)»**, el panel en Render **aún no tiene** `/api/argus-admin/v1/*`.

Comprobación:

```powershell
curl https://asperss.onrender.com/api/argus-admin/v1/status
```

Debe devolver JSON (`product: ArgusAdmin`). Si devuelve HTML 404 → **git push** del repo (carpeta `web_app/` con `argus_admin_api.py`) y esperar el deploy en Render.

### Mientras tanto (solo en tu PC)

1. `BAT\INICIAR_PANEL_LOCAL.bat`
2. `%APPDATA%\ArgusAdmin\config.json` → `"api_url": "http://127.0.0.1:8080"`
3. En `web_app\.env.local`: `ARGUS_ADMIN_JWT_SECRET` (mismo valor que usarás en Render)
4. Regrabar voz en ArgusAdmin

## Variables en Render (producción)

Variables en Render:

```env
ARGUS_ADMIN_JWT_SECRET=<secreto-largo>
ARGUS_PANEL_OWNER_USERNAMES=Rodrigo
SUPER_ADMIN_USER=Rodrigo
SUPER_ADMIN_PASS=<tu-clave-super-admin>
# Si Rodrigo solo existe como SUPER_ADMIN (no en tabla users):
ARGUS_ADMIN_LINK_USER_ID=1
```

`/aspers-sa` usa `SUPER_ADMIN_USER` / `SUPER_ADMIN_PASS`. ArgusAdmin acepta esas mismas credenciales y guarda la voz vinculada al `user_id` de `ARGUS_ADMIN_LINK_USER_ID` (o al primer owner que exista en la BD).

## Checklist al probar

1. Configurar `api_url` y `username` en la app o en `%APPDATA%\ArgusAdmin\config.json`
2. **Regrabar voz** (3 muestras) tras actualizar a v0.1.1+
3. Desbloquear con voz + contraseña owner del panel
4. Abrir `/aspers-sa` desde el dashboard desbloqueado

Ver troubleshooting completo en [`argus-admin/README.md`](../argus-admin/README.md).
