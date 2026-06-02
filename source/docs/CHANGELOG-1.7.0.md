# Argus Scanner 1.7.0

## Qué hace esta actualización

Argus Scanner 1.7 es una versión orientada a **Screen Share forense en Minecraft**: más superficies de detección, menos fricción al iniciar y datos offline dentro del ejecutable para trabajar aunque la API tarde en responder.

## Novedades principales

### Pack forense (89 módulos)

- **28 `pkg_*`** — Todo el directorio `scanners/` (clipboard, ETW, Cobalt, browser history, etc.).
- **28 `forensic_*`** — Cada técnica de `SSForensics` por separado (USN, AppCompat, UserAssist, …).
- **30 `nov_*`** — Launchers, remote (AnyDesk, RustDesk), periféricos, Bedrock, Game Bar, etc.
- **3 `mine_*`** — Minado automático (Baritone, macros, procesos).

Configurable en el .exe: botón **Beta** o `Ctrl+Shift+M`.

### Arranque sin “petardazo”

- Validación del token en **hilo de fondo** (timeout corto, sin bloquear Tk).
- Motor pesado (DB, forensics, IA, mouse) en **segundo plano** con pantalla “Preparando motor…”.
- Hashes cloud y modelo IA se refrescan **después**, si hay red.

### Paquete offline embebido (~53 MiB real, sin relleno)

- `scanner_db.sqlite` — patrones aprendidos.
- `offline_hash_catalog.bin` — miles de SHA256 para lookup sin internet.
- `offline_lexicon.json` — firmas de hacks/mods.
- `offline_scan_profile.json` — reglas de rutas del escaneo.
- `docs/staff_guide_offline.html` — guía rápida dentro del .exe.
- Assets UI (splash 4K/5K) y ZIP de referencia de módulos.

### Mouse / prison mode

- Detección en vivo: botón sostenido, patrón mecánico, plug/unplug durante SS.
- **Uso pasado:** setupapi.dev.log, Event Log PnP, Prefetch, BAM, registro USB/HID.
- Veredicto resumen: `MOUSE_WEIGHT_PAST_USAGE`.

### Licencia SS y panel

- Descarga **“para SS”** con `argus_lic_*` embebida — autenticación automática.
- Filtros de empresa vía API (`/api/scanner/filter-rules`).
- IA aprende falsos positivos (cron + envío desde el cliente).

## Compilar

```powershell
cd source
powershell -ExecutionPolicy Bypass -File scripts\build_dist_60.ps1
```

Salida: `dist_60/ArgusScanner.exe` y copia a `dist_new3/`.
