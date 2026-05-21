# ArgusAdmin — Control Imperial

**Producto activo** del ecosistema ASPERS (prioridad de desarrollo).

Independiente del Argus Scanner. **Argus Assistant** queda en pausa como proyecto futuro.

SuperAdmin de escritorio conectado a **Render**, desbloqueado con **tu voz** en este PC.

## Flujo de seguridad

1. Solo el **owner del panel** (`ARGUS_PANEL_OWNER_USERNAMES`, ej. `arefy_admin`).
2. **Grabás 3 muestras** de tu frase (ej. «desbloqueo argus»).
3. La huella se guarda **local** + hash en PostgreSQL (Render).
4. Cada vez que abrís ArgusAdmin: **voz + contraseña** → token 12h con permisos ampliados.
5. Sin tu voz, aunque roben la contraseña, no obtienen token `voice_ok`.

> La voz no es biometría bancaria: grabá en un lugar tranquilo y no compartas el WAV. Es una barrera fuerte frente a acceso remoto casual.

## Render (variables)

```env
ARGUS_ADMIN_JWT_SECRET=genera-un-secreto-largo
ARGUS_PANEL_OWNER_USERNAMES=arefy_admin
```

## Uso

```powershell
BAT\INICIAR_ARGUS_ADMIN.bat
```

### Si falla login o la voz (v0.1.1+)

| Problema | Qué hacer |
|----------|-----------|
| «respuesta no es JSON» / vacío | Render dormido: esperá ~30 s; la app reintenta solo. URL: `https://asperss.onrender.com` |
| «Voz no coincide» tras regrabar | Usá **Regrabar voz** (borra perfil viejo y pide 3 muestras de nuevo) |
| «Voz no registrada en el servidor» | Regrabar con internet; debe decir «Voz registrada en Render» |
| Micrófono sin audio | Mensaje claro si el WAV está vacío; subí volumen del mic |
| Umbral muy estricto | En `%APPDATA%\ArgusAdmin\config.json` → `"voice_threshold": 0.40` (default 0.45) |

Tras actualizar el servidor en Render, el enroll guarda **todos** los hashes de las 3 muestras (más tolerante al desbloquear).

## Configuración local

`%APPDATA%\ArgusAdmin\config.json`:

```json
{
  "api_url": "https://asperss.onrender.com",
  "username": "arefy_admin",
  "phrase": "desbloqueo argus",
  "voice_threshold": 0.45
}
```

Desde la app: **1. Configurar cuenta y API** antes de grabar la voz.

## .exe

```powershell
cd argus-admin
pip install -r requirements.txt
python -m PyInstaller ArgusAdmin.spec --noconfirm
scripts\copiar_a_escritorio.bat
```

Tras compilar, el `.exe` se copia al **escritorio** (`ArgusAdmin-vX.Y.Z.exe`) y se borran los `ArgusAdmin*.exe` viejos que hubiera ahí.

## Permisos (token desbloqueado)

`sa.overview`, `sa.companies`, `sa.users`, `sa.maintenance`, `sa.ai_weights`, `sa.audit`, `scanner.version`, `platform.config`, `assistant.config.write`
