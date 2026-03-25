#!/usr/bin/env bash
# MindLakeVM - 一键启动脚本（前后端同时启动）

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 清理函数：脚本退出时关闭子进程
cleanup() {
  echo ""
  echo "==> 正在关闭服务..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  echo "==> 已关闭"
}
trap cleanup EXIT INT TERM

echo "=============================="
echo "  MindLakeVM 开发环境启动"
echo "=============================="
echo ""

# 启动后端
echo "[1/2] 启动后端..."
bash "$ROOT_DIR/mindlakevm/runtime/start.sh" &
BACKEND_PID=$!

# 等待后端就绪
echo "      等待后端就绪..."
for i in $(seq 1 20); do
  if curl -s http://localhost:8000/docs > /dev/null 2>&1; then
    echo "      后端已就绪 ✓"
    break
  fi
  sleep 0.5
done

echo ""

# 启动前端
echo "[2/2] 启动前端..."
bash "$ROOT_DIR/mindlakevm/ui/start.sh" &
FRONTEND_PID=$!

echo ""
echo "=============================="
echo "  服务已启动"
echo "  前端:    http://localhost:5173"
echo "  后端:    http://localhost:8000"
echo "  API文档: http://localhost:8000/docs"
echo "  按 Ctrl+C 停止所有服务"
echo "=============================="

# 等待子进程
wait "$BACKEND_PID" "$FRONTEND_PID"
