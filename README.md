# Argus Projects

[![Stars](https://img.shields.io/github/stars/SkzfXrolo/AsperSS?style=for-the-badge)](https://github.com/SkzfXrolo/AsperSS/stargazers)
[![CI](https://img.shields.io/badge/ci-pack48--active-brightgreen?style=for-the-badge)](./.github/workflows)
[![Plugin Downloads](https://img.shields.io/github/downloads/SkzfXrolo/AsperSS/total?style=for-the-badge)](https://github.com/SkzfXrolo/AsperSS/releases)
[![License](https://img.shields.io/badge/license-REVIEW-lightgrey?style=for-the-badge)](#licencia)
[![Version](https://img.shields.io/badge/version-0.1.0-informational?style=for-the-badge)](#)
[![Java 21](https://img.shields.io/badge/java-21-blue?style=for-the-badge)](https://adoptium.net/)

Argus Projects unifica componentes para anti-cheat: web app Flask, scanner desktop y plugin Minecraft con telemetria de violaciones.

## Componentes

- `web_app/`: panel web y rutas de descarga.
- `source/`: scanner desktop Python.
- `minecraft_plugin/argus-mc/`: plugin Bukkit/Paper.
- `scripts/`: automatizaciones de build y release.
- `docs/`: guias tecnicas y operativas.

## Plataformas soportadas

| Plataforma | Estado | Entregable |
| --- | --- | --- |
| Linux | Activo | AppImage, DEB, RPM, Snap/Flatpak/AUR |
| macOS | Activo | `.app`, `.dmg`, firma/notarizacion |
| Android | Activo | APK, AAB, firma y distribución |
| Docker/K8s | Activo | Compose, manifests y Helm |

## Quick install por OS

- Linux: revisar `scripts/linux/` y `docs/linux/`.
- macOS: revisar `docs/macos/install-guide.md`.
- Android: revisar `scripts/android/` y `docs/android/`.
- Self-host: revisar `docs/self-hosting/quick-start.md`.

## Build rapido plugin

```bash
cd minecraft_plugin/argus-mc
mvn -B -ntp clean package
```

## Licencia

REVIEW: definir licencia oficial del proyecto (`LICENSE*` pendiente de confirmacion).
