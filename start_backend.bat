@echo off
chcp 65001 >nul
title MBAM Backend

echo [시스템] 8000번 포트를 사용하는 기존 서버가 있는지 확인하고 정리합니다...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo [시스템] 충돌하는 기존 프로세스 (PID: %%a)를 강제로 종료합니다.
    taskkill /F /PID %%a >nul 2>&1
)
echo [시스템] 정리가 완료되었습니다. 서버를 새롭게 시작합니다!
echo.

python run_backend.py
pause
