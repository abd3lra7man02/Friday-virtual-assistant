@echo off
setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         FRIDAY ASSISTANT - DIAGNOSTIC SCRIPT                ║
echo ║              Run this to find what's broken                 ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

set "PROJECT_DIR=C:\Users\FreeComp\Desktop\Python virtual environment\friday"
set "HUD_DIR=%PROJECT_DIR%\friday-hud"

REM Check .env file
echo [1/8] Checking .env file...
if not exist "%PROJECT_DIR%\.env" (
    echo ❌ .env file not found!
    pause
    exit /b 1
) else (
    echo ✓ .env found
    for /f "tokens=2 delims==" %%A in ('findstr "^FRIDAY_API_KEY=" "%PROJECT_DIR%\.env"') do set "API_TOKEN=%%A"
    set "API_TOKEN=!API_TOKEN: =!"
    if "!API_TOKEN!"=="" (
        echo ❌ FRIDAY_API_KEY is empty!
        pause
        exit /b 1
    ) else (
        echo ✓ API_TOKEN found: !API_TOKEN:~0,10!...
    )
)

REM Check Python
echo.
echo [2/8] Checking Python installation...
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Python is NOT in PATH or not installed!
    echo    Try: python --version
    pause
    exit /b 1
) else (
    for /f "tokens=2" %%A in ('python --version 2^>^&1') do echo ✓ Python found: %%A
)

REM Check virtual environment
echo.
echo [3/8] Checking virtual environment...
if not exist "%PROJECT_DIR%\friday_env\Scripts\activate.bat" (
    echo ❌ Virtual environment not found at: %PROJECT_DIR%\friday_env
    pause
    exit /b 1
) else (
    echo ✓ Virtual environment found
)

REM Check pip packages
echo.
echo [4/8] Checking Python dependencies...
call "%PROJECT_DIR%\friday_env\Scripts\activate.bat" > nul 2>&1
pip show fastapi > nul 2>&1
if errorlevel 1 (
    echo ❌ FastAPI not installed!
    echo    Run: pip install -r requirements.txt
    pause
    exit /b 1
) else (
    echo ✓ FastAPI installed
)

pip show uvicorn > nul 2>&1
if errorlevel 1 (
    echo ❌ Uvicorn not installed!
    echo    Run: pip install uvicorn
    pause
    exit /b 1
) else (
    echo ✓ Uvicorn installed
)

REM Check Node.js
echo.
echo [5/8] Checking Node.js installation...
node --version > nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js is NOT in PATH or not installed!
    echo    Download from: https://nodejs.org/
    pause
    exit /b 1
) else (
    for /f "tokens=1" %%A in ('node --version 2^>^&1') do echo ✓ Node.js found: %%A
)

REM Check npm
echo.
echo [6/8] Checking npm...
npm --version > nul 2>&1
if errorlevel 1 (
    echo ❌ npm is NOT available!
    pause
    exit /b 1
) else (
    for /f "tokens=1" %%A in ('npm --version 2^>^&1') do echo ✓ npm found: %%A
)

REM Check React HUD directory
echo.
echo [7/8] Checking React HUD setup...
if not exist "%HUD_DIR%" (
    echo ❌ friday-hud directory not found!
    pause
    exit /b 1
) else (
    echo ✓ friday-hud directory found
)

if not exist "%HUD_DIR%\node_modules" (
    echo ⚠ node_modules not found - installing...
    cd /d "%HUD_DIR%"
    call npm install
    cd /d "%PROJECT_DIR%"
) else (
    echo ✓ node_modules found
)

REM Check Ollama
echo.
echo [8/8] Checking Ollama connection...
curl -s http://localhost:11434/api/tags > nul 2>&1
if errorlevel 1 (
    echo ⚠ Ollama is NOT running
    echo   Start it with: ollama serve
) else (
    echo ✓ Ollama is running
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         ✓ ALL DIAGNOSTICS PASSED!                           ║
echo ║                                                              ║
echo ║  You can now run RUN.bat                                    ║
echo ║  Or run START_MANUAL.bat to see detailed output             ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

pause
