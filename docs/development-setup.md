# Desarrollo local

## Requisitos

- Python 3.11+
- Java 21 (plugin)
- Maven 3.9+
- Node/Android SDK solo para app movil

## Setup rapido

```bash
git clone <repo>
cd aspersprojectsSS-main
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Componentes

- Web app Flask: revisar `web_app/`.
- Scanner Python: revisar `source/`.
- Plugin Minecraft: `minecraft_plugin/argus-mc` (`mvn clean package`).

## Panel local (réplica Render)

Ver guía completa: [local-dev-render.md](local-dev-render.md)

```bat
BAT\INICIAR_PANEL_LOCAL.bat
```

→ http://127.0.0.1:8080/panel (misma BD que producción si configuras `web_app/.env.local`)

## Scripts utiles

- Panel local: `BAT/INICIAR_PANEL_LOCAL.bat`, `scripts/dev/start-local-panel.ps1`
- Linux packaging: `scripts/linux/*`
- Android build helpers: `scripts/android/*`
- Changelog: `scripts/build/gen-changelog.sh`
