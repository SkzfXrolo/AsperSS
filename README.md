# Argus Projects

[![Stars](https://img.shields.io/github/stars/SkzfXrolo/AsperSS?style=for-the-badge)](https://github.com/SkzfXrolo/AsperSS/stargazers)
[![Plugin Downloads](https://img.shields.io/github/downloads/SkzfXrolo/AsperSS/total?style=for-the-badge)](https://github.com/SkzfXrolo/AsperSS/releases)
[![License](https://img.shields.io/badge/license-REVIEW-lightgrey?style=for-the-badge)](#licencia)
[![Java 21](https://img.shields.io/badge/java-21-blue?style=for-the-badge)](https://adoptium.net/)

Argus Projects unifica componentes para anti-cheat: web app Flask, scanner desktop y plugin Minecraft con telemetria de violaciones.

## Componentes

- `web_app/`: panel web y rutas de descarga.
- `source/`: scanner desktop Python.
- `minecraft_plugin/argus-mc/`: plugin Bukkit/Paper.
- `scripts/`: automatizaciones de build y release.
- `docs/`: guias tecnicas y operativas.

## Build rapido plugin

```bash
cd minecraft_plugin/argus-mc
mvn -B -ntp clean package
```

## Licencia

REVIEW: definir licencia oficial del proyecto (`LICENSE*` pendiente de confirmacion).
