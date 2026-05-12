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

## Scripts utiles

- Linux packaging: `scripts/linux/*`
- Android build helpers: `scripts/android/*`
- Changelog: `scripts/build/gen-changelog.sh`
