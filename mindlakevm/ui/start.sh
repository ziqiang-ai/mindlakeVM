#!/usr/bin/env bash
# MindLakeVM UI - 前端启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> 启动 MindLakeVM 前端 (Vite/React)"
echo "    地址: http://localhost:5173"
echo ""

if [ ! -d "node_modules" ]; then
  echo "[提示] 未找到 node_modules，正在安装依赖..."
  npm install
fi

exec npm run dev
