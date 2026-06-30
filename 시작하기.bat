@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MBAM 실행기

echo ==========================================
echo   MBAM 마케팅 프로그램 시작
echo ==========================================

REM ── venv 설치 여부 확인 ─────────────────────────
if not exist "venv\Scripts\python.exe" (
  echo [오류] 설치가 안 되어 있습니다. 먼저 "설치하기.bat" 을 실행하세요.
  pause
  exit /b 1
)

REM ── 인증코드 확인 (PC 1대당) ────────────────────────
echo [인증] 인증코드 확인 중...
venv\Scripts\python -c "from mbam_auth_gate import run_auth_gate; import sys; sys.exit(0 if run_auth_gate() else 1)"
if errorlevel 1 (
  echo [인증 실패] 인증되지 않아 프로그램을 종료합니다.
  pause
  exit /b 1
)

REM ── 기존 서버 포트 정리 (8000=백엔드, 3000=화면) ──
echo [시스템] 기존 서버 정리 중...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

REM ── 백엔드(핵심 엔진) 시작 ──────────────────────
echo [1/2] 백엔드 서버(8000) 시작...
start "MBAM Backend (8000)" cmd /k "cd /d "%~dp0" && set "PYTHONPATH=%~dp0" && venv\Scripts\python run_backend.py"

REM ── 프론트엔드(화면) 시작 ───────────────────────
echo [2/2] 화면 서버(3000) 시작...
start "MBAM Frontend (3000)" cmd /k "cd /d "%~dp0mbam-web" && npm run dev"

echo.
echo 잠시 후 브라우저가 자동으로 열립니다... (처음엔 화면 준비에 10~20초 걸립니다)
timeout /t 8 >nul
start http://localhost:3000

echo 완료! 이 창은 닫아도 됩니다. (서버 창 2개는 켜둔 채로 사용하세요)
timeout /t 3 >nul
exit
