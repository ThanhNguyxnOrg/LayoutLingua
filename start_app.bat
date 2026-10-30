@echo off
title LayoutLingua AI Translation Studio
echo ========================================================
echo          LayoutLingua AI Translation Studio
echo ========================================================

cd /d "%~dp0"

where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Node.js is required but not found in PATH.
    echo Please install Node.js 18+ from https://nodejs.org/ to proceed.
    pause
    exit /b 1
)

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Python is required but not found in PATH.
    echo Please install Python 3.10+ from https://python.org/ to proceed.
    pause
    exit /b 1
)

if not exist "node_modules" (
    echo [*] First-time setup: installing Node dependencies...
    call npm install --legacy-peer-deps
)

echo [*] Launching LayoutLingua Web Studio (Vite + Python Engine)...
start "" http://localhost:3000
npm run dev
