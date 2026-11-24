#!/usr/bin/env bash
# 一鍵啟動：建置並啟動系統 UI＋模擬信箱，完成後自動開啟兩個頁面
set -euo pipefail
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "找不到 docker，請先安裝 Docker Desktop：https://www.docker.com/products/docker-desktop/"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker 沒有在執行，請先打開 Docker Desktop"; exit 1; }
export AUDITBOX_WORKSPACE="${AUDITBOX_WORKSPACE:-$PWD/workspace}"
mkdir -p "$AUDITBOX_WORKSPACE"
export AUDITBOX_WORKSPACE_LABEL="${AUDITBOX_WORKSPACE/#$HOME/~}"
echo "工作區：$AUDITBOX_WORKSPACE_LABEL"
docker compose up -d --build
printf "等待服務啟動"
for _ in $(seq 1 60); do
  if curl -fs http://localhost:8765/api/meta >/dev/null 2>&1; then echo " 完成"; break; fi
  printf "."; sleep 2
done
opener=$(command -v open || command -v xdg-open || true)
if [ -n "$opener" ]; then "$opener" http://localhost:8765; "$opener" http://localhost:8025; fi
echo "系統 UI：http://localhost:8765"
echo "模擬信箱：http://localhost:8025"
echo "停止服務：docker compose down"
