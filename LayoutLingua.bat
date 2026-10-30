@echo off
setlocal
title LayoutLingua Desktop Application
cd /d "%~dp0"

:: 1. If standalone compiled .exe already exists and --build-exe was not requested, launch it directly
if /I not "%~1"=="--build-exe" (
    if exist "release\LayoutLingua\LayoutLingua.exe" (
        start "" "release\LayoutLingua\LayoutLingua.exe"
        exit /b 0
    )
)

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Python 3.10+ is required to run LayoutLingua from source.
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

:: 2. Build frontend production bundle once if dist\index.html does not exist
if not exist "dist\index.html" (
    where node >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [!] Node.js 18+ is required for first-time UI compilation.
        pause
        exit /b 1
    )
    if not exist "node_modules" (
        echo [*] Installing UI dependencies...
        call npm install --legacy-peer-deps
    )
    echo [*] Compiling LayoutLingua Desktop UI...
    call npm run build
)

:: 3. Ensure Python engine + native desktop window library (pywebview) are installed
python -c "import pymupdf, webview" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [*] Installing LayoutLingua Python engine and native Desktop WebView2 host...
    python -m pip install -r requirements.txt pywebview
)

:: 4. If user passed --build-exe, package into standalone release\LayoutLingua\LayoutLingua.exe
if /I "%~1"=="--build-exe" (
    echo [*] Building standalone Windows Desktop Application (.exe)...
    python -m layoutlingua.desktop --build-exe
    pause
    exit /b %ERRORLEVEL%
)

:: 5. Launch native Desktop Application window (without opening a web browser tab)
where pythonw >nul 2>nul
if %ERRORLEVEL% equ 0 (
    start "" pythonw -m layoutlingua.desktop
) else (
    python -m layoutlingua.desktop
)
