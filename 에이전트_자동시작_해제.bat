@echo off
title 마케팅연구소 에이전트 - 자동시작 해제

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\마케팅연구소_에이전트.vbs"

if exist "%LAUNCHER%" (
  del /f /q "%LAUNCHER%"
  echo [완료] 자동시작 등록을 해제했습니다. (다음 부팅부터 자동 실행 안 함)
) else (
  echo [안내] 등록된 자동시작이 없습니다.
)

echo.
echo * 지금 실행 중인 에이전트는 작업 관리자에서 pythonw.exe 를 종료하면 멈춥니다.
pause
