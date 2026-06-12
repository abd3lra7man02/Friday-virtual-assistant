@echo off
setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         FRIDAY ASSISTANT - REACT HUD STARTUP                ║
echo ║              (Run this in a separate terminal)               ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.

set "PROJECT_DIR=C:\Users\FreeComp\Desktop\Python virtual environment\friday"
set "HUD_DIR=%PROJECT_DIR%\friday-hud"

REM Extract token
for /f "tokens=2 delims==" %%A in ('findstr "^FRIDAY_API_KEY=" "%PROJECT_DIR%\.env"') do set "API_TOKEN=%%A"
set "API_TOKEN=!API_TOKEN: =!"

echo [SYSTEM] Configuration:
echo          HUD Directory: %HUD_DIR%
echo          Token: !API_TOKEN:~0,10!...
echo.

REM Check Node version
echo [SYSTEM] Node.js version:
node --version
echo.

REM Check npm version
echo [SYSTEM] npm version:
npm --version
echo.

REM Install dependencies if needed
if not exist "%HUD_DIR%\node_modules" (
    echo [SYSTEM] Installing npm dependencies (first run)...
    cd /d "%HUD_DIR%"
    call npm install
    if errorlevel 1 (
        echo ❌ ERROR: npm install failed
        pause
        exit /b 1
    )
) else (
    echo ✓ npm dependencies already installed
)
echo.

REM Start dev server
echo [SYSTEM] Starting Vite development server...
echo          Command: npm run dev
echo.
echo ┌────────────────────────────────────────────────────────────┐
echo │                  Vite Output:                              │
echo ├────────────────────────────────────────────────────────────┤

cd /d "%HUD_DIR%"
call npm run dev

echo.
echo │────────────────────────────────────────────────────────────│
echo └────────────────────────────────────────────────────────────┘
echo.
echo ❌ Vite dev server stopped
echo.

pause
