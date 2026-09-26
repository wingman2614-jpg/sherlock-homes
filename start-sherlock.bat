@echo off
REM Sherlock Homes Mk2 - one-click launcher
REM Put this file in C:\sherlock-homes-mk2 and double-click it.

cd /d "%~dp0"

echo Stopping any old copies on ports 8000 and 3000...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"

if not exist ".venv\Scripts\activate.bat" (
  echo Python environment not found. Run the first-time setup in README.md first.
  pause
  exit /b 1
)

echo Starting the backend (API) in a new window...
start "Sherlock API" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate.bat && uvicorn api.main:app --port 8000"

echo Starting the website in a new window...
start "Sherlock Website" cmd /k "cd /d %~dp0web && npm run dev"

echo Waiting for the website to start...
timeout /t 12 /nobreak >nul
start "" http://localhost:3000

echo.
echo Sherlock Homes Mk2 is starting. Two windows opened:
echo   - "Sherlock API"      (keep it open)
echo   - "Sherlock Website"  (keep it open)
echo To stop Sherlock, close those two windows.
echo For Dr. John's AI answers, make sure the Ollama app is running.
timeout /t 8 >nul
