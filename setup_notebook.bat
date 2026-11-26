@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python 3 was not found. Install Python 3 and try again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 (
        echo Could not create the notebook environment.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Could not install notebook dependencies. Check your internet connection and try again.
    pause
    exit /b 1
)

echo Notebook environment is ready. Select .venv as the notebook interpreter.
pause
