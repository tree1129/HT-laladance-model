#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROBOT_HOST="${1:-192.168.43.44}"
ROBOT_USER="${2:-hightorque}"
REMOTE_BASE="/home/${ROBOT_USER}/robot_remote_web_agent"

echo "Deploying robot agent to ${ROBOT_USER}@${ROBOT_HOST}:${REMOTE_BASE}"
ssh "${ROBOT_USER}@${ROBOT_HOST}" "mkdir -p '${REMOTE_BASE}'"
rsync -av --delete "${ROOT_DIR}/robot_agent/" "${ROBOT_USER}@${ROBOT_HOST}:${REMOTE_BASE}/robot_agent/"

cat <<EOF

部署完成。
机器人上启动：
  ssh ${ROBOT_USER}@${ROBOT_HOST}
  cd ${REMOTE_BASE}/robot_agent
  bash start_robot_agent.sh

浏览器访问：
  http://${ROBOT_HOST}:8766
EOF
