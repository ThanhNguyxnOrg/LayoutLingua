@echo off
title LayoutLingua Web Studio Launcher
echo ========================================================
echo          LayoutLingua AI Translation Studio
echo ========================================================

cd /d "%~dp0"

echo [*] Launching LayoutLingua Web Studio (Vite + Python Engine)...
start "" http://localhost:3000
npm run dev
