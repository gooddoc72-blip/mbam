#!/bin/bash

# 스크립트가 실행되는 디렉토리로 이동
cd "$(dirname "$0")"

echo "======================================"
echo "라이선스 서버 및 관리자 시스템 구동 중..."
echo "======================================"

# 가상환경 활성화
source venv/bin/activate
cd license_server

# 이미 8005 포트를 쓰고 있는 서버가 있다면 종료시킴 (포트 충돌 방지)
lsof -ti:8005 | xargs kill -9 2>/dev/null

# 백그라운드에서 FastAPI 서버 구동
uvicorn server:app --port 8005 &
SERVER_PID=$!

echo "서버가 성공적으로 실행되었습니다. (포트: 8005)"
echo "관리자 대시보드를 엽니다..."

# 관리자 대시보드 UI 띄우기 (이 창을 닫기 전까지 프로그램이 여기서 대기함)
python3 admin_dashboard.py

# 관리자 대시보드 창의 X버튼을 눌러서 닫으면, 아래 코드가 실행되며 서버도 같이 꺼짐
echo "관리자 대시보드가 종료되었습니다. 서버를 안전하게 끕니다."
kill $SERVER_PID
echo "모든 프로그램이 종료되었습니다."
exit 0
