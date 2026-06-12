@echo off
setlocal enabledelayedexpansion

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║         FRIDAY ASSISTANT - STARTUP SCRIPT                   ║
echo ║   Follow the instructions carefully for proper startup      ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
set "PROJECT_DIR=C:\Users\FreeComp\Desktop\Python virtual environment\friday"
set "HUD_DIR=%PROJECT_DIR%\friday-hud"

REM Step 1: Check .env and token
echo [STEP 1/4] Verifying configuration...
if not exist "%PROJECT_DIR%\.env" (
    echo ❌ ERROR: .env file not found!
    echo    Expected at: %PROJECT_DIR%\.env
    pause
    exit /b 1
)

for /f "tokens=2 delims==" %%A in ('findstr "^FRIDAY_API_KEY=" "%PROJECT_DIR%\.env"') do set "API_TOKEN=%%A"
set "API_TOKEN=!API_TOKEN: =!"
if "!API_TOKEN!"=="" (
    echo ❌ ERROR: FRIDAY_API_KEY is empty in .env!
    pause
    exit /b 1
)

echo ✓ Configuration verified
echo   Token: !API_TOKEN:~0,15!...
echo.
REM Step 2: Check Ollama
echo [STEP 2/4] Checking Ollama...
curl -s http://localhost:11434/api/tags > nul 2>&1
if errorlevel 1 (
    echo ⚠ WARNING: Ollama is NOT running
    echo   To start Ollama, open a new terminal and run: ollama serve
    echo   Then come back and run this script again
    echo.
    set /p CONTINUE="Continue anyway? (Y/N): "
    if /i not "!CONTINUE!"=="Y" exit /b 1
) else (
    echo ✓ Ollama is running
)
echo.
REM Step 3: Kill old processes
echo [STEP 3/4] Starting servers (killing old instances)...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM node.exe /T >nul 2>&1
timeout /t 2 /nobreak > nul
echo ✓ Old processes cleaned up
echo.
REM Step 4: Start services
echo [STEP 4/4] Launching services...
echo.

echo ╔════════════════════════════════════════════════════╗
echo ║  IMPORTANT: Three terminal windows will open.      ║
echo ║  Keep all of them open for Friday to work.        ║
echo ║  Close this window when done.                     ║
echo ╚════════════════════════════════════════════════════╝
echo.

echo Opening Backend (FastAPI) in new window...
start "FRIDAY Backend - Keep This Open" cmd /c "%PROJECT_DIR%\.venv\Scripts\activate && cd /d "%PROJECT_DIR%" && python -m uvicorn server:app --host 0.0.0.0 --port 8000 --log-level info && pause"

timeout /t 3 /nobreak > nul

echo Opening Frontend (React HUD) in new window...
start "FRIDAY HUD - Keep This Open" cmd /c "cd /d "%HUD_DIR%" && npm run dev && pause"

timeout /t 5 /nobreak > nul

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║                  OPENING FRIDAY HUD                         ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
set "HUD_URL=http://localhost:5173/?token=!API_TOKEN!"

echo URL: !HUD_URL!
echo.

if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" --app="!HUD_URL!"
) else if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --app="!HUD_URL!"
) else (
    echo ℹ Chrome not found in standard location
    echo   Open this URL manually: !HUD_URL!
)

echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║              STARTUP COMPLETE                               ║
echo ║                                                              ║
echo ║  You should now see:                                         ║
echo ║  1. Backend window (FastAPI output)                         ║
echo ║  2. Frontend window (Vite dev server)                       ║
echo ║  3. Chrome window with Friday HUD                           ║
echo ║                                                              ║
echo ║  If something is missing:                                    ║
echo ║  - Check the background windows for errors                 ║
echo ║  - Run DIAGNOSE.bat to check your setup                     ║
echo ║  - Run START_BACKEND.bat or START_FRONTEND.bat manually   ║
echo ║                                                              ║
echo ║  Press any key to close this window                         ║
echo ║  (The servers will keep running)                            ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
pause