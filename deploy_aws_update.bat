@echo off
chcp 65001 >nul
echo [AWS 서버 업데이트 진행] 변경된 서버 코드를 AWS로 업로드합니다...
echo.

cd /d "%~dp0"

echo 1. AWS 서버로 최신 소스코드 복사 중... (잠시 대기해 주세요)
scp -o StrictHostKeyChecking=no -i my-key.pem -r auth_server ubuntu@18.209.162.250:~/

if %errorlevel% neq 0 (
    echo.
    echo [오류] 소스코드 전송에 실패했습니다. (키 파일 확인 필요)
    pause
    exit /b %errorlevel%
)

echo.
echo 2. AWS 서버 접속 및 Docker 컨테이너 재시작 중...
ssh -o StrictHostKeyChecking=no -i my-key.pem ubuntu@18.209.162.250 "cd auth_server && sudo docker compose up -d --build"

if %errorlevel% neq 0 (
    echo.
    echo [오류] 서버 재구동에 실패했습니다.
    pause
    exit /b %errorlevel%
)

echo.
echo ========================================================
echo 완료! AWS 클라우드 인증 서버 업데이트가 무사히 적용되었습니다.
echo ========================================================
pause
