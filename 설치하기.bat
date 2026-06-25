@echo off
chcp 65001 >nul
cd /d "%~dp0"
title MBAM 설치 마법사

echo ==========================================
echo   MBAM 마케팅 프로그램 - 노트북 설치
echo ==========================================
echo.

REM ── 1. Python 확인 ──────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
  echo [오류] Python 이 설치되어 있지 않습니다.
  echo        https://www.python.org/downloads/ 에서 Python 3.12 이상을 설치하고
  echo        설치 시 "Add Python to PATH" 를 꼭 체크한 뒤 이 파일을 다시 실행하세요.
  pause
  exit /b 1
)

REM ── 2. Node.js 확인 ─────────────────────────────
node --version >nul 2>&1
if errorlevel 1 (
  echo [오류] Node.js 가 설치되어 있지 않습니다.
  echo        https://nodejs.org 에서 LTS 버전을 설치한 뒤 이 파일을 다시 실행하세요.
  pause
  exit /b 1
)

echo [확인] Python / Node.js 설치 확인 완료.
echo.

REM ── 3. 가상환경(venv) 생성 ──────────────────────
if not exist "venv" (
  echo [1/6] 파이썬 가상환경(venv) 생성 중...
  python -m venv venv
) else (
  echo [1/6] 기존 가상환경 발견 - 건너뜀.
)

REM ── 4. pip 업그레이드 ───────────────────────────
echo [2/6] pip 업그레이드...
venv\Scripts\python -m pip install --upgrade pip >nul

REM ── 5. 백엔드 패키지 설치 ───────────────────────
echo [3/6] 파이썬 패키지 설치 중... (시간이 걸립니다)
venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 (
  echo [오류] 파이썬 패키지 설치에 실패했습니다. 인터넷 연결을 확인하세요.
  pause
  exit /b 1
)

REM ── 6. Playwright 크로미움 설치 ─────────────────
echo [4/6] 자동화 브라우저(Chromium) 설치 중...
venv\Scripts\python -m playwright install chromium

REM ── 7. 보안 키 생성/확인 ────────────────────────
echo [5/6] 보안 키(JWT/암호화) 확인 및 생성...
venv\Scripts\python setup_secrets.py

REM ── 8. 프론트엔드 패키지 설치 ───────────────────
echo [6/6] 화면(프론트엔드) 패키지 설치 중...
cd mbam-web
call npm install
if errorlevel 1 (
  echo [오류] 프론트엔드 패키지 설치 실패. Node.js 설치를 확인하세요.
  cd ..
  pause
  exit /b 1
)
cd ..

echo.
echo ==========================================
echo   설치 완료!  "시작하기.bat" 으로 실행하세요.
echo ==========================================
echo.
echo  * 네이버 계정은 노트북에서 [설정 - 계정관리 - 기기인증] 을
echo    1회 다시 진행해야 자동 로그인이 됩니다. (기기 인증은 PC마다 별도)
echo.
pause
