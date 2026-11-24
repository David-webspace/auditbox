#!/bin/sh
set -e
WS=/workspace
if [ ! -f "$WS/00_設定/設定.yaml" ]; then
  echo "工作區是空的，放入 12 件展示資料"
  cp -R /app/demo/. "$WS"/
fi
exec auditbox serve "$WS" --host 0.0.0.0 --port 8765 --no-browser
