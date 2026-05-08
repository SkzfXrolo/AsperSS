# ArgusScanner Linux

Variante Linux del Argus Scanner. Mismo backend, mismo panel staff, pero
con heurísticas y fuentes de evidencia nativas Linux. Cubre los siguientes
ítems del `MEJORAS_180.txt` (sección Plataforma Linux):

- ✅ #1 — paquete separado `argus_linux/` que no toca al `.exe` Windows
- ✅ #2 — `import winreg` aislado: este paquete no lo usa, solo usa stdlib
- ✅ #3 — papelera XDG (`~/.local/share/Trash`) + Trash en mounts no-home
- ✅ #4 — `journalctl --user` últimas 72h + bash/zsh/fish history
- ✅ #6 — `/proc/<pid>/{cmdline,maps,environ}` + LD_PRELOAD detection
- ✅ #7 — ventanas: `wmctrl` (X11) + `gdbus` (GNOME-Wayland)
- ✅ #8 — launchers MC: oficial, Prism, MultiMC, ATLauncher, GDLauncher,
        PolyMC, Modrinth, Flatpak (`~/.var/app/...`), snap
- ✅ #9 — screenshot: `grim` (wlroots) → `gnome-screenshot` → `spectacle`
        → `scrot` → `import` → `maim` (auto-detección)
- 🟡 #5 — auditd/USN equivalente: dejado como TODO (requiere config root)
- 🟡 #10/#11/#12 — empaquetado AppImage/Flatpak/deb: TODO (de momento se
        distribuye como `.tar.gz` con script + carpeta)
- 🟡 #14 — CI E2E sobre Docker: TODO

## Quickstart para tu tester

```bash
# 1) Bajar el paquete
curl -L -o argus-linux.tar.gz "https://asperss.onrender.com/descargar/linux"
tar -xzf argus-linux.tar.gz
cd argus_linux

# 2) Pedir el token al staff (panel.argus → Generar token)

# 3) Correr (usuario normal, NO sudo)
chmod +x run-argus.sh
./run-argus.sh TU_TOKEN_AQUI
```

## Dependencias

Casi todo es stdlib. Para captura de pantalla pedimos UNA de estas tools
del sistema (no pip):

| Servidor gráfico | Paquete recomendado |
|---|---|
| Wayland (Hyprland/Sway/wlroots) | `grim` |
| Wayland (GNOME) | `gnome-screenshot` |
| Wayland (KDE) | `kde-spectacle` |
| X11 | `scrot` o `imagemagick` (`import`) o `maim` |

Si no hay ninguna disponible, el scanner sigue corriendo y solo omite
la captura (te lo advierte).

## Modo offline / smoke test

```bash
# Genera reporte JSON local sin tocar el backend
./run-argus.sh fake-token --offline

# Smoke test: no requiere token válido (pero no sube nada)
./run-argus.sh fake-token --scan-self
```

El reporte queda en `/tmp/argus_lin_report_<timestamp>.json`.

## Diferencias honestas vs. la versión Windows

Cosas que **NO** cubre la versión Linux (por diseño técnico):

- No hay `Prefetch`, `Amcache`, `ShimCache` ni `USN Journal`
- No hay registry → no hay equivalente a Run/RunOnce hooks (pero sí hay
  `~/.config/autostart/*.desktop` + systemd user units que iremos
  cubriendo en próximas versiones)
- No hay `Defender Quarantine` ni `ASR events`
- Captura de ventanas en Wayland depende del compositor (KDE-Wayland
  todavía no expone window titles fácil sin scripts kwin)

Cosas que **SÍ** cubre la versión Linux:

- `LD_PRELOAD` activo → vector clásico de inyección Linux que el .exe
  Windows ni siquiera contempla (porque no aplica)
- `/proc/<pid>/maps` para listar `.jar`/`.so` cargados en java vivo
- Trash en cualquier mount, no solo `~/.local/share/Trash`
- Browser history en paths Linux (`~/.config/google-chrome/...`,
  `~/.var/app/...` para Flatpak)

## Arquitectura interna

```
source/argus_linux/
├── __init__.py          # versión + docstring
├── __main__.py          # entry point para `python3 -m argus_linux`
├── scanner.py           # todo monolítico (~700 líneas)
├── run-argus.sh         # wrapper con detección de tools y mensajes amigables
├── requirements.txt     # lista de paquetes del SO recomendados
└── README.md            # este archivo
```

Sin dependencias pip. Funciona con Python 3.9+ que viene en cualquier
distro mainstream actual.
