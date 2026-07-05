@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 마케팅연구소 에이전트 - 자동시작 등록

REM ============================================================
REM  이 PC가 켜질 때(로그인 시) 에이전트가 자동으로 백그라운드
REM  실행되도록 Windows 시작프로그램에 등록합니다. (1회만 실행)
REM  → 이후에는 수동으로 에이전트를 켤 필요가 없습니다.
REM ============================================================

set "APP=%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\마케팅연구소_에이전트.vbs"

if not exist "agent_config.json" (
  echo [안내] agent_config.json 이 없습니다.
  echo        먼저 agent_config.example.json 을 복사해 계정 정보를 채워주세요.
  pause
  exit /b 1
)

REM 파이썬 실행기 결정 (동봉 venv 우선, 없으면 시스템 pythonw)
if exist "venv\Scripts\pythonw.exe" (
  set "PYW=%APP%venv\Scripts\pythonw.exe"
) else (
  set "PYW=pythonw"
)

REM 콘솔창 없이 백그라운드로 에이전트를 실행하는 VBS 런처 생성(시작프로그램에 배치)
> "%LAUNCHER%" echo Set sh = CreateObject("WScript.Shell")
>> "%LAUNCHER%" echo sh.CurrentDirectory = "%APP%"
>> "%LAUNCHER%" echo sh.Environment("PROCESS")("PYTHONPATH") = "%APP%"
>> "%LAUNCHER%" echo sh.Run """%PYW%"" ""%APP%agent.py""", 0, False

echo.
echo [완료] Windows 시작 시 에이전트가 자동 실행되도록 등록했습니다.
echo         (시작프로그램: %LAUNCHER%)
echo.
echo 지금 바로 에이전트를 실행합니다...
start "" wscript "%LAUNCHER%"
echo.
echo * 해제하려면: 에이전트_자동시작_해제.bat
echo * 잘 켜졌는지 확인: 작업 관리자 - 세부정보 - pythonw.exe
pause
