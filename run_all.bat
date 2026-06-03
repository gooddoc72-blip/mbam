@echo off
echo ==========================================
echo MBAM NextGen - Auto Server Starter
echo ==========================================

cd /d "C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램"

echo [1/2] Starting Python Backend Server...
start "MBAM Backend (Port 8000)" /MIN cmd /c "set PYTHONPATH=C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램 && python -m uvicorn mbam_nextgen.backend.main:app --host 0.0.0.0 --port 8000"

echo [2/2] Starting Next.js Frontend Server...
cd mbam-web
start "MBAM Frontend (Port 3000)" /MIN cmd /c "npm run dev"

echo All servers are starting in the background!
timeout /t 3
exit
