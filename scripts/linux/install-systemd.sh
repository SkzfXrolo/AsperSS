#!/usr/bin/env bash
set -euo pipefail

sudo install -Dm644 scripts/linux/systemd/argus-web.service /etc/systemd/system/argus-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now argus-web
echo "OK: servicio argus-web instalado."
