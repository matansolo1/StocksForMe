@echo off
setlocal

REM ============================================================
REM  StocksForMe - One-Click Launcher
REM  Installs dependencies directly on the system Python (no
REM  virtual environment) and starts the Flask server.
REM  The browser opens automatically once the server is ready
REM  (handled from within app.py).
REM ============================================================

REM Always run from this script's own folder, regardless of
REM where it was launched from (double-click, shortcut, etc.)
cd /d "%~dp0"

echo ================================================
echo   StocksForMe - Starting Application
echo ================================================
echo.

REM --- 1. Check that Python is installed and available ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found on this computer.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM --- 2. Install required packages directly on the system Python ---
echo [Setup] Checking/installing required packages...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)

echo.
echo ================================================
echo   Launching server on http://127.0.0.1:5000
echo   The browser will open automatically.
echo   Keep this window open while using the app.
echo   Close this window (or press Ctrl+C) to stop.
echo ================================================
echo.

python app.py

echo.
echo Server stopped.
pause
