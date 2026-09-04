#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
cd "$PROJECT_DIR"

exec python3 -m uvicorn service.app:app --host 127.0.0.1 --port "${AI_HOTSPOT_PORT:-8765}"
