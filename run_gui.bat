@echo off
title LayoutLingua Desktop
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app\gui.py %*
) else (
    python app\gui.py %*
)
