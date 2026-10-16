@echo off
title LayoutLingua Desktop Launcher
echo ========================================================
echo       LayoutLingua Native Desktop Application
echo ========================================================

cd /d "%~dp0"

echo [1/2] Checking Python backend engine...
powershell -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1).StatusCode } catch { exit 1 }" >nul 2>&1
if %errorlevel% equ 0 (
    echo   - Backend server is already running on port 8765.
) else (
    echo   - Starting background backend engine...
    start "" /b ".venv\Scripts\python.exe" -m layoutlingua.server
    timeout /t 2 >nul
)

echo [2/2] Launching Native Desktop App...
start "" "desktop\src-tauri\target\release\layoutlingua-desktop.exe"

echo Done! LayoutLingua is now running.
