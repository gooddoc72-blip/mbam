@echo off
chcp 65001 >nul
echo ==========================================
echo MBAM NextGen - Auto Server Starter
echo ==========================================

cd /d "C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램"

echo [시스템] 기존 켜져있는 서버들을 모두 깔끔하게 종료하는 중...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo [1/2] 파이썬 백엔드(핵심 엔진) 서버를 시작합니다...
start "MBAM Backend (Port 8000)" cmd /k "set PYTHONPATH=C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램 && python run_backend.py"

echo [2/2] 화면(UI) 서버를 시작합니다...
cd mbam-web
start "MBAM Frontend (Port 3000)" cmd /k "npm run dev"

echo 모든 서버가 정상적으로 켜졌습니다! 약 3초 뒤 이 창은 닫힙니다.
timeout /t 3
exit
