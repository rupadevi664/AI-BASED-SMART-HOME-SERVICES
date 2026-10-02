@echo off
title AI Smart Home Services Launcher
echo ========================================================
echo   Starting AI Smart Home Services (Backend + Frontend)
echo ========================================================
echo.

echo Starting Backend Server (FastAPI on Port 8000)...
start "Backend - FastAPI (Port 8000)" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo Starting Frontend Server (React Vite on Port 5173)...
start "Frontend - React Vite (Port 5173)" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================================
echo   Both servers have been launched!
echo   - Frontend: http://localhost:5173
echo   - Backend API Docs: http://127.0.0.1:8000/docs
echo   - Live Location Demo: http://127.0.0.1:8000/location-demo
echo ========================================================
