@echo off
chcp 65001 > nul
set /a count=1

:loop
if %count% GTR 50 goto end
echo =========================================
echo [배치 %count%회차 시작]
echo =========================================

echo [1단계] 네트워크 리셋 실행...
node reset_network.js

echo [2단계] 모바일 UI 및 검색 검증 실행...
node qa_test.js

echo [3단계] 다음 회차 진입 대기 (20초)...
timeout /t 20 /nobreak > nul

set /a count+=1
goto loop

:end
echo 모든 테스트 배치가 완료되었습니다.
pause