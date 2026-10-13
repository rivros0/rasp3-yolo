#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
if [[ "$(uname -m)" != "aarch64" ]]; then
    echo "Serve Raspberry Pi OS a 64 bit (aarch64)." >&2
    exit 1
fi
python3 -c 'import sys; assert (3, 10) <= sys.version_info[:2] <= (3, 12), "Usare Python 3.10-3.12; consigliato Raspberry Pi OS Bookworm 64 bit"'
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git curl v4l-utils libopenblas-dev libjpeg-dev zlib1g-dev libgl1 libglib2.0-0
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-rpi.txt
sudo usermod -aG video "$(id -un)"
v4l2-ctl --list-devices
.venv/bin/python -c 'from ultralytics import YOLO; YOLO("yolov8n.pt")'
echo "Installazione completata. Esegui: bash scripts/install_service.sh"
