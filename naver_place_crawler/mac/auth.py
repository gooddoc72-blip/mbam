import subprocess
import hashlib
import requests
import json
import os

import platform

def get_server_url():
    home_dir = os.path.expanduser("~")
    url_path = os.path.join(home_dir, ".crawler_server.txt")
    if os.path.exists(url_path):
        try:
            with open(url_path, "r") as f:
                return f.read().strip()
        except:
            pass
    return ""

def set_server_url(url):
    global AUTH_SERVER_URL
    AUTH_SERVER_URL = url
    home_dir = os.path.expanduser("~")
    url_path = os.path.join(home_dir, ".crawler_server.txt")
    try:
        with open(url_path, "w") as f:
            f.write(url)
    except:
        pass

AUTH_SERVER_URL = get_server_url()
_cached_hwid = None

def get_hwid():
    """
    PC 메인보드의 고유 UUID를 추출하여 SHA-256 해시값으로 변환한 HWID를 생성합니다.
    Windows 및 macOS를 모두 지원합니다.
    """
    global _cached_hwid
    if _cached_hwid:
        return _cached_hwid
        
    try:
        system = platform.system()
        uuid_str = ""

        if system == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.check_output('wmic csproduct get uuid', startupinfo=startupinfo, text=True)
            uuid_str = result.split('\n')[1].strip()
            
        elif system == "Darwin": # macOS 환경 (빠른 ioreg 명령어로 교체)
            result = subprocess.check_output(['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'], text=True)
            for line in result.split('\n'):
                if "IOPlatformUUID" in line:
                    uuid_str = line.split('=')[1].strip().replace('"', '')
                    break
            if not uuid_str:
                raise Exception("macOS UUID를 찾을 수 없습니다.")
                
        else:
            raise Exception(f"지원하지 않는 운영체제입니다: {system}")

        hwid = hashlib.sha256(uuid_str.encode('utf-8')).hexdigest()
        _cached_hwid = hwid
        return hwid
    except Exception as e:
        print(f"HWID 추출 실패: {e}")
        return "UNKNOWN_HWID"

def get_license_key_path():
    home_dir = os.path.expanduser("~")
    return os.path.join(home_dir, ".crawler_license.key")

def verify_pc_online():
    """
    온라인 서버에 HWID를 보내 이 PC가 승인되었는지 확인합니다.
    승인된 경우 로컬에 암호화된 영구 라이선스 키를 저장하여 이후 오프라인으로 작동합니다.
    """
    hwid = get_hwid()
    if hwid == "UNKNOWN_HWID":
        return False, "기기 정보를 읽을 수 없습니다.", hwid

    if not AUTH_SERVER_URL:
        return False, "SERVER_URL_MISSING", hwid

    SECRET_SALT = "MySuperSecretCrawlerKey2026_For_Offline!"
    expected_key = hashlib.sha256((hwid + SECRET_SALT).encode('utf-8')).hexdigest()
    license_path = get_license_key_path()

    # 1. 오프라인 영구 라이선스 키가 있는지 확인
    if os.path.exists(license_path):
        try:
            with open(license_path, "r") as f:
                saved_key = f.read().strip()
            if saved_key == expected_key:
                return True, "오프라인 영구 인증 완료", hwid
        except:
            pass

    # 2. 오프라인 키가 없거나 불일치하면 서버와 통신 시도
    try:
        response = requests.post(
            AUTH_SERVER_URL, 
            json={"hwid": hwid},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("authorized", False):
                # 서버에서 최종 승인 시, 오프라인 라이선스 키 발급(저장)
                try:
                    with open(license_path, "w") as f:
                        f.write(expected_key)
                except:
                    pass
                return True, "approved", hwid
            else:
                status = data.get("status", "unknown")
                return False, status, hwid
        else:
            return False, "서버 연결 오류", hwid
            
    except requests.exceptions.RequestException as e:
        return False, "인증 서버에 연결할 수 없습니다. 인터넷 연결을 확인하세요.", hwid
    except Exception as e:
        return False, f"서버 요청 실패: {e}", hwid

if __name__ == "__main__":
    # 단독 실행 시 테스트
    success, msg, hwid = verify_pc_online()
    print(f"내 PC 기기 번호(HWID): {hwid}")
    print(f"인증 결과: {success} ({msg})")
