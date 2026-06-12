@echo off
echo [SYSTEM] Booting FRIDAY Core Logic...
:: Start the Python Backend in a new minimized window
start "FRIDAY Backend" /MIN cmd /c "cd /d "C:\Users\FreeComp\Desktop\Python virtual environment\friday" && call .\friday_env\Scripts\activate && uvicorn server:app"

echo [SYSTEM] Initializing Visual HUD...
:: Start the React Frontend in a new minimized window
start "FRIDAY HUD" /MIN cmd /c "cd /d "C:\Users\FreeComp\Desktop\Python virtual environment\friday\friday-hud" && npm run dev"

echo [SYSTEM] Waiting for servers to come online...
:: Wait for 4 seconds to ensure the local servers are running
timeout /t 4 /nobreak > NUL

echo [SYSTEM] Opening Interface...
:: Open Chrome in App Mode for a borderless, native feel
start chrome --app=http://localhost:5173/

exit