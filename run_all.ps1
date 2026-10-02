# Run both backend and frontend concurrently
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Starting AI Smart Home Services (Backend + Frontend)   " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$backendDir = Join-Path $PSScriptRoot "backend"
$frontendDir = Join-Path $PSScriptRoot "frontend"

Write-Host "Starting Backend (FastAPI on Port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$backendDir'; & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

Write-Host "Starting Frontend (React Vite on Port 5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$frontendDir'; npm run dev"

Write-Host "`nBoth servers have been launched!" -ForegroundColor Green
Write-Host "Frontend:            http://localhost:5173" -ForegroundColor White
Write-Host "Backend API Docs:    http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "Live Location Demo:  http://127.0.0.1:8000/location-demo" -ForegroundColor White
