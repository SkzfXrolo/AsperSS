"""ArgusScanner Linux — variante para Linux desktop (Plataforma #1, #2).

El scanner Windows (source/main.py) sigue intacto. Este paquete contiene
una implementación standalone para Linux que comparte el mismo contrato
de API con el backend (POST /api/scans + POST /api/scans/<id>/results)
pero usa fuentes de evidencia nativas de Linux:

  - Papelera XDG (~/.local/share/Trash) en lugar de $RECYCLE.BIN
  - journalctl + bash/zsh/fish history en lugar de Prefetch
  - /proc/<pid>/{cmdline,maps,status,exe} en lugar de psutil-only
  - LD_PRELOAD detection (vector Linux clásico)
  - X11 (wmctrl/xdotool) y Wayland (gdbus/qdbus) para ventanas
  - grim / scrot / ImageMagick / portal XDG para screenshots
  - SQLite de browser history desde paths Linux

Entry point: argus_linux.scanner:main (correr `python3 -m argus_linux`).
"""

__version__ = '1.6.45-linux1'
