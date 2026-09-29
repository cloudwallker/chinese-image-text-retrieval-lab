@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 请先运行：powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
    pause
    exit /b 1
)
".venv\Scripts\python.exe" app.py --open
if errorlevel 1 pause
