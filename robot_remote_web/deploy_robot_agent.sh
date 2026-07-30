#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROBOT_HOST="${1:-192.168.18.114}"
ROBOT_USER="${2:-hightorque}"
REMOTE_BASE="${3:-/home/${ROBOT_USER}/robot_remote_web_agent}"

echo "Deploying robot agent to ${ROBOT_USER}@${ROBOT_HOST}:${REMOTE_BASE}"
ssh "${ROBOT_USER}@${ROBOT_HOST}" "mkdir -p '${REMOTE_BASE}'"
rsync -av --delete "${SCRIPT_DIR}/robot_agent/" "${ROBOT_USER}@${ROBOT_HOST}:${REMOTE_BASE}/robot_agent/"

cat <<EOF

Deployment finished.

Start it on the robot:
  ssh ${ROBOT_USER}@${ROBOT_HOST}
  cd ${REMOTE_BASE}/robot_agent
  bash start_robot_agent.sh

Then open this URL in your browser:
  http://${ROBOT_HOST}:8766
EOF
