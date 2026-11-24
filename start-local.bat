@echo off
chcp 65001 > nul
cd /d %~dp0
if "%~1"=="" (set WORKSPACE=demo) else (set WORKSPACE=%~1)
where uv > nul 2>&1 || (
  echo 找不到 uv，請先安裝：https://docs.astral.sh/uv/
  pause
  exit /b 1
)
if not exist web\out\index.html (
  echo 找不到前端檔案 web\out，請先在 web 資料夾執行 pnpm install ^&^& pnpm build
  pause
  exit /b 1
)
echo 啟動模具請款稽核，工作資料夾：%WORKSPACE%
uv run auditbox serve "%WORKSPACE%"
pause
