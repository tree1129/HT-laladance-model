#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Stopping local virtual remote if it is running..."
pkill -f "${SCRIPT_DIR}/server.py" || true
pkill -f "robot_remote_web/server.py" || true
sleep 1

echo "Starting local virtual remote from ${SCRIPT_DIR}..."
cd "$SCRIPT_DIR"
if command -v python3 >/dev/null 2>&1; then
  exec python3 server.py
fi
exec python server.py
