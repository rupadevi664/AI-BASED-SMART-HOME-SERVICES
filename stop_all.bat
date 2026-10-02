@echo off
title Stop AI Smart Home Services
echo ========================================================
echo   Stopping AI Smart Home Services (Ports 8000 and 5173)
echo ========================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped PID: ' + $_) }"

echo.
echo Servers stopped.
pause
