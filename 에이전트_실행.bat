@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 마케팅연구소 에이전트

REM [방법 B] 웹 관제형 로컬 에이전트 실행
REM   - 웹(marketlabs.kr)에서 분석을 요청하면 이 PC가 집 IP로 대신 처리합니다.
REM   - 최초 1회: agent_config.example.json 을 복사해 agent_config.json 을 만들고
REM     cloud_url / email / password 를 채워주세요.

if not exist "agent_config.json" (
  echo [안내] agent_config.json 이 없습니다.
  echo        agent_config.example.json 을 복사해 계정 정보를 채운 뒤 다시 실행하세요.
  pause
  exit /b 1
)

set "MBAM_MODE=agent"
set "PYTHONPATH=%~dp0"

if exist "venv\Scripts\python.exe" (
  venv\Scripts\python mbam_launcher.py
) else (
  python mbam_launcher.py
)
