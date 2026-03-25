#!/usr/bin/env bash
# MindLakeVM Runtime - 后端启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD="${RELOAD:-true}"

echo "==> 启动 MindLakeVM 后端 (FastAPI)"
echo "    地址: http://${HOST}:${PORT}"
echo "    API 文档: http://localhost:${PORT}/docs"
echo ""

if [ ! -d ".venv" ]; then
  echo "[错误] 未找到 .venv 虚拟环境，请先执行: uv sync"
  exit 1
fi

RELOAD_FLAG=""
if [ "$RELOAD" = "true" ]; then
  RELOAD_FLAG="--reload"
fi

exec .venv/bin/uvicorn main:app \
  --host "$HOST" \
  --port "$PORT" \
  $RELOAD_FLAG
