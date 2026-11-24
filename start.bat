@echo off
chcp 65001 > nul
cd /d %~dp0
REM 一鍵啟動：建置並啟動系統 UI＋模擬信箱，完成後自動開啟兩個頁面
where docker > nul 2>&1 || (
  echo 找不到 docker，請先安裝 Docker Desktop：https://www.docker.com/products/docker-desktop/
  pause
  exit /b 1
)
docker info > nul 2>&1 || (
  echo Docker 沒有在執行，請先打開 Docker Desktop
  pause
  exit /b 1
)
if "%AUDITBOX_WORKSPACE%"=="" set "AUDITBOX_WORKSPACE=%CD%\workspace"
if not exist "%AUDITBOX_WORKSPACE%" mkdir "%AUDITBOX_WORKSPACE%"
REM 畫面只顯示 ~ 開頭的路徑，截圖不會露出帳號名稱
call set "AUDITBOX_WORKSPACE_LABEL=%%AUDITBOX_WORKSPACE:%USERPROFILE%=~%%"
echo 工作區：%AUDITBOX_WORKSPACE_LABEL%
docker compose up -d --build || (
  pause
  exit /b 1
)
echo 等待服務啟動...
powershell -NoProfile -Command "for($i=0;$i -lt 60;$i++){try{Invoke-WebRequest -UseBasicParsing http://localhost:8765/api/meta | Out-Null; exit 0}catch{Start-Sleep 2}}; exit 1"
start "" http://localhost:8765
start "" http://localhost:8025
echo 系統 UI：http://localhost:8765
echo 模擬信箱：http://localhost:8025
echo 停止服務：docker compose down
pause
