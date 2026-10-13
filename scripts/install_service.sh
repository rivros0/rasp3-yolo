#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE="/etc/systemd/system/rasp3-yolo.service"
SERVICE_USER="$(id -un)"
if [[ "$SERVICE_USER" == "root" ]]; then
    echo "Eseguire come utente normale: bash scripts/install_service.sh" >&2
    exit 1
fi
test -x "$PROJECT_DIR/.venv/bin/python"

sudo tee "$SERVICE_FILE" >/dev/null <<SERVICE
[Unit]
Description=Raspberry Pi YOLO Lab
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/.venv/bin/python -m app.main --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
User=$SERVICE_USER
SupplementaryGroups=video
Environment=PYTHONUNBUFFERED=1
Environment=OMP_NUM_THREADS=2

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable --now rasp3-yolo
echo "Servizio installato: sudo systemctl status rasp3-yolo"
