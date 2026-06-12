@echo off
setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         FRIDAY ASSISTANT - MANUAL STARTUP                   ║
echo ║              (Shows all output - debug version)              ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

set "PROJECT_DIR=C:\Users\FreeComp\Desktop\Python virtual environment\friday"
set "HUD_DIR=%PROJECT_DIR%\friday-hud"

REM Extract token
for /f "tokens=2 delims==" %%A in ('findstr "^FRIDAY_API_KEY=" "%PROJECT_DIR%\.env"') do set "API_TOKEN=%%A"
set "API_TOKEN=!API_TOKEN: =!"

echo [SYSTEM] Configuration:
echo          Project: %PROJECT_DIR%
echo          Token: !API_TOKEN:~0,10!...
echo.

REM Kill old processes
echo [SYSTEM] Cleaning up old processes...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1
timeout /t 1 /nobreak > nul
echo ✓ Old processes terminated
echo.

REM Check if ports are free
echo [SYSTEM] Checking if ports are available...
netstat -ano | findstr :8000 > nul 2>&1
if not errorlevel 1 (
    echo ⚠ WARNING: Port 8000 is already in use
    echo   Process using port 8000:
    netstat -ano | findstr :8000
    echo.
)

netstat -ano | findstr :5173 > nul 2>&1
if not errorlevel 1 (
    echo ⚠ WARNING: Port 5173 is already in use
)
echo.

REM Activate virtual environment and check
echo [SYSTEM] Activating Python virtual environment...
call "%PROJECT_DIR%\friday_env\Scripts\activate.bat"
if errorlevel 1 (
    echo ❌ ERROR: Failed to activate virtual environment
    echo    Path: %PROJECT_DIR%\friday_env\Scripts\activate.bat
    pause
    exit /b 1
)
echo ✓ Virtual environment activated
echo.

REM Show Python version
echo [SYSTEM] Python version:
python --version
echo.

REM Show pip installed packages
echo [SYSTEM] Checking FastAPI/Uvicorn...
pip list | findstr fastapi
pip list | findstr uvicorn
echo.

REM Start FastAPI server
echo [SYSTEM] Starting FastAPI server...
echo          Command: python -m uvicorn server:app --host 0.0.0.0 --port 8000
echo.
echo ┌────────────────────────────────────────────────────────────┐
echo │                  FastAPI Output:                           │
echo ├────────────────────────────────────────────────────────────┤

cd /d "%PROJECT_DIR%"
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --log-level info

echo.
echo │────────────────────────────────────────────────────────────│
echo └────────────────────────────────────────────────────────────┘
echo.
echo ❌ FastAPI server stopped or failed
echo.

pause
