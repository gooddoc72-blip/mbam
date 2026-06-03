@echo off
echo ==========================================
echo Marketing Program Launcher
echo ==========================================

echo [1/3] Installing Python backend dependencies...
pip install -r requirements.txt
python -m playwright install chromium

echo [2/3] Installing Frontend dependencies...
cd mbam-web
call npm install
cd ..

echo [3/3] Starting servers...
start cmd /k "python run_backend.py"
start cmd /k "cd mbam-web && npm run dev"

timeout /t 5 >nul
start http://localhost:3000

echo All set! You can close this window.
pause
