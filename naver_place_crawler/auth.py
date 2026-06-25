import subprocess
import hashlib
import requests
import json
import os

import platform

# 인증 서버의 주소입니다. (실제 서버 도메인이나 IP로 변경해야 합니다)
# 예: http://your-server.com/api/verify_hwid
AUTH_SERVER_URL = "http://127.0.0.1:8005/verify"

def get_hwid():
    """
    PC 메인보드의 고유 UUID를 추출하여 SHA-256 해시값으로 변환한 HWID를 생성합니다.
    Windows 및 macOS를 모두 지원합니다.
    """
    try:
        system = platform.system()
        uuid_str = ""

        if system == "Windows":
            # Windows 환경에서 메인보드 UUID 추출
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.check_output('wmic csproduct get uuid', startupinfo=startupinfo, text=True)
            uuid_str = result.split('\n')[1].strip()
            
        elif system == "Darwin": # macOS 환경
            result = subprocess.check_output(['system_profiler', 'SPHardwareDataType'], text=True)
            for line in result.split('\n'):
                if "Hardware UUID" in line or "UUID" in line:
                    uuid_str = line.split(':')[1].strip()
                    break
            if not uuid_str:
                raise Exception("macOS UUID를 찾을 수 없습니다.")
                
        else:
            raise Exception(f"지원하지 않는 운영체제입니다: {system}")

        # UUID를 기반으로 해시 생성 (보안 및 규격화를 위해)
        hwid = hashlib.sha256(uuid_str.encode('utf-8')).hexdigest()
        return hwid
    except Exception as e:
        print(f"HWID 추출 실패: {e}")
        return "UNKNOWN_HWID"

def verify_pc_online():
    """
    온라인 서버에 HWID를 보내 이 PC가 승인되었는지 확인합니다.
    """
    hwid = get_hwid()
    if hwid == "UNKNOWN_HWID":
        return False, "기기 정보를 읽을 수 없습니다.", hwid

    try:
        # 서버에 인증 요청 (예: POST 요청으로 hwid 전달)
        response = requests.post(
            AUTH_SERVER_URL, 
            json={"hwid": hwid},
            timeout=5 # 5초 안에 응답이 없으면 실패 처리
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("authorized", False):
                return True, "인증 성공", hwid
            else:
                return False, "등록되지 않은 기기입니다. 관리자에게 승인을 요청하세요.", hwid
        else:
            # 테스트/로컬 환경에서 서버가 꺼져있을 경우 우회를 원한다면 이 부분을 수정하세요.
            return False, f"서버 통신 오류 (상태코드: {response.status_code})", hwid
            
    except requests.exceptions.RequestException as e:
        return False, "인증 서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요.", hwid

if __name__ == "__main__":
    # 단독 실행 시 테스트
    success, msg, hwid = verify_pc_online()
    print(f"내 PC 기기 번호(HWID): {hwid}")
    print(f"인증 결과: {success} ({msg})")
