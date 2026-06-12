# 🚀 FRIDAY ASSISTANT - STARTUP GUIDE

## **Quick Start (3 Steps)**

### **Step 1: Run Diagnostic**
Double-click `DIAGNOSE.bat` - this will check if everything is installed and working.

**Expected output:**
```
✓ .env found
✓ API_TOKEN found
✓ Python found: Python 3.x.x
✓ Virtual environment found
✓ FastAPI installed
✓ Uvicorn installed
✓ Node.js found: v18.x.x
✓ npm found: 9.x.x
✓ friday-hud directory found
✓ node_modules found
✓ Ollama is running
```

**If any checks fail**, the diagnostic will tell you exactly what to fix.

---

### **Step 2: Start Ollama (if not running)**
Open PowerShell or CMD and run:
```bash
ollama serve
```
Keep this window open - Ollama needs to stay running.

---

### **Step 3: Run Friday**
Double-click `RUN.bat` - this will:
1. ✓ Extract your authentication token from `.env`
2. ✓ Kill any old processes
3. ✓ Open 3 new windows (Backend, Frontend, Chrome)
4. ✓ Automatically load the HUD with authentication

You should see:
- **Window 1**: Backend (FastAPI) - Shows `Uvicorn running on http://0.0.0.0:8000`
- **Window 2**: Frontend (Vite) - Shows `Local: http://localhost:5173`
- **Window 3**: Chrome HUD - Shows Friday interface with **CONNECTED** status

---

## **If Something Goes Wrong**

### **Chrome Won't Open / Shows "CONNECTING..."**

**Try this:**
1. Open PowerShell
2. Copy and paste:
```powershell
$token = (Get-Content "C:\Users\FreeComp\Desktop\Python virtual environment\friday\.env" | Select-String "FRIDAY_API_KEY").ToString().Split("=")[1].Trim()
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" "--app=http://localhost:5173/?token=$token"
```

---

### **Backend Window Closes Immediately**

**Run this instead:**
Double-click `START_BACKEND.bat` - this shows all errors in a window that stays open.

**Common issues:**
- ❌ `ModuleNotFoundError: No module named 'fastapi'`
  - **Fix:** Run `pip install -r requirements.txt`

- ❌ `ModuleNotFoundError: No module named 'server'`
  - **Fix:** Make sure you're in the correct directory

- ❌ `Address already in use: 0.0.0.0:8000`
  - **Fix:** Port 8000 is occupied. Run in PowerShell:
    ```powershell
    netstat -ano | findstr :8000
    taskkill /PID <PID_NUMBER> /F
    ```

---

### **Frontend Window Closes Immediately**

**Run this instead:**
Double-click `START_FRONTEND.bat`

**Common issues:**
- ❌ `npm: command not found`
  - **Fix:** Node.js not installed. Download from https://nodejs.org/

- ❌ `EACCES: permission denied`
  - **Fix:** Run Command Prompt **as Administrator**

- ❌ `port 5173 already in use`
  - **Fix:**
    ```bash
    netstat -ano | findstr :5173
    taskkill /PID <PID_NUMBER> /F
    ```

---

### **HUD Shows "AUTH ERROR" or "CONNECTING..." Stuck Yellow**

**Check:**
1. Is `.env` file in the project root?
   ```bash
   dir "C:\Users\FreeComp\Desktop\Python virtual environment\friday\.env"
   ```

2. Does it have `FRIDAY_API_KEY`?
   ```bash
   type "C:\Users\FreeComp\Desktop\Python virtual environment\friday\.env" | findstr FRIDAY_API_KEY
   ```

3. Is backend running?
   ```bash
   curl http://localhost:8000/health
   ```

If not running, check the Backend window for errors.

---

### **Ollama Shows "My brain is offline"**

This is **normal on first query** - Ollama is loading the model (llama3 is ~4.7GB).
Just wait 30-60 seconds and try again.

**To pre-load the model:**
```bash
ollama pull llama3
ollama pull nomic-embed-text
```

---

## **Manual Startup (If You Prefer Individual Control)**

### **Terminal 1: Start Ollama**
```bash
ollama serve
```

### **Terminal 2: Start Backend**
```bash
cd "C:\Users\FreeComp\Desktop\Python virtual environment\friday"
.\friday_env\Scripts\activate
python -m uvicorn server:app --host 0.0.0.0 --port 8000 --log-level info
```

### **Terminal 3: Start Frontend**
```bash
cd "C:\Users\FreeComp\Desktop\Python virtual environment\friday\friday-hud"
npm run dev
```

### **Terminal 4 (or Browser): Open HUD**
```powershell
# Get token from .env
$token = (Get-Content "C:\Users\FreeComp\Desktop\Python virtual environment\friday\.env" | Select-String "FRIDAY_API_KEY").ToString().Split("=")[1].Trim()

# Open in Chrome
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" "--app=http://localhost:5173/?token=$token"
```

---

## **Verify Everything Works**

### **Test Backend**
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"ok","ollama":"online","version":"1.0.0"}`

### **Test Frontend**
```bash
curl http://localhost:5173
```
Expected: HTML content (status 200)

### **Test Ollama**
```bash
curl http://localhost:11434/api/tags
```
Expected: List of loaded models

---

## **Troubleshooting by Symptom**

| Symptom | Cause | Solution |
|---------|-------|----------|
| Chrome won't open | Browser closed | Open URL manually: `http://localhost:5173/?token=...` |
| HUD shows CONNECTING | Backend not running | Run `START_BACKEND.bat` and check for errors |
| HUD shows AUTH ERROR | Token mismatch | Copy token from `.env` file into browser URL |
| Port 8000 in use | Old process still running | `taskkill /F /IM python.exe` |
| npm modules missing | First run of frontend | `cd friday-hud && npm install` |
| "Ollama offline" message | Ollama crashed or not started | Start with `ollama serve` in separate terminal |
| Hold F2 doesn't record | Using voice.py instead of HUD | Use the HUD interface (Chrome window) instead |

---

## **File Reference**

| File | Purpose |
|------|---------|
| `RUN.bat` | Main startup script (recommended) |
| `DIAGNOSE.bat` | Check your setup for issues |
| `START_BACKEND.bat` | Debug backend startup |
| `START_FRONTEND.bat` | Debug frontend startup |
| `.env` | Configuration (token, city, timezone) |

---

## **Getting Help**

**Check logs:**
```bash
# Backend log
tail -f "C:\Users\FreeComp\Desktop\Python virtual environment\friday\friday_server.log"

# Brain log
tail -f "C:\Users\FreeComp\Desktop\Python virtual environment\friday\friday_brain.log"
```

**Browser console:**
1. Press `F12` in Chrome HUD
2. Click "Console" tab
3. Look for red error messages

---

**Now run `RUN.bat` and Friday should come online! 🎉**
