#!/bin/bash
set -e

echo "停止本地远程服务..."
pkill -f "python3 server.py" || true
sleep 1

echo "启动本地远程服务..."
cd "$(dirname "$0")"
python3 server.py
