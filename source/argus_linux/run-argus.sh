#!/usr/bin/env bash
# ArgusScanner Linux — wrapper de ejecución portable.
# Detecta python3 disponible, opcionalmente recomienda paquetes de captura
# de pantalla, y lanza el scanner.
#
# Uso:
#   ./run-argus.sh <TOKEN>
#   ./run-argus.sh <TOKEN> --no-screenshot
#   ./run-argus.sh <TOKEN> --server https://otro.host
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 no está instalado. Instalá con tu package manager:"
    echo "   sudo apt install python3            # Debian/Ubuntu"
    echo "   sudo dnf install python3            # Fedora"
    echo "   sudo pacman -S python               # Arch"
    exit 2
fi

if [ "$#" -lt 1 ]; then
    echo "❌ Falta el TOKEN."
    echo
    echo "Uso: $0 <TOKEN> [opciones]"
    echo
    echo "Opciones útiles:"
    echo "  --no-screenshot       No capturar pantalla (headless / VPS)"
    echo "  --offline             No subir nada al servidor, solo JSON local"
    echo "  --server <URL>        Backend custom (default: https://asperss.onrender.com)"
    echo "  --scan-self           Smoke test offline (sin token válido)"
    echo
    exit 1
fi

# Recomendaciones de tools de screenshot si no hay ninguna
if [ -z "${ARGUS_SKIP_SS_HINT:-}" ]; then
    HAS_SS=0
    for tool in grim scrot import gnome-screenshot spectacle maim; do
        if command -v "$tool" >/dev/null 2>&1; then
            HAS_SS=1
            break
        fi
    done
    if [ "$HAS_SS" -eq 0 ]; then
        echo "⚠ No se detectó ninguna tool de screenshot. Para capturar pantalla, instalá UNA de:"
        echo "   Wayland (Hyprland/Sway):  sudo pacman -S grim       /  sudo apt install grim"
        echo "   X11:                     sudo apt install scrot   /  sudo dnf install scrot"
        echo "   GNOME:                   sudo apt install gnome-screenshot"
        echo "   KDE:                     sudo apt install kde-spectacle"
        echo "   Fallback genérico:       sudo apt install imagemagick"
        echo "   (o pasá --no-screenshot para saltar este paso)"
        echo
    fi
fi

# Lanzar scanner como módulo. Subimos un nivel (source/) para que
# 'argus_linux' sea importable como paquete.
cd "$SCRIPT_DIR/.."
exec python3 -m argus_linux "$@"
