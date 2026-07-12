import platform
import os
import subprocess
import time

def find_adb():
    if platform.system() == "Windows":
        return "adb"
    # Common macOS paths
    paths = [
        "/usr/local/bin/adb",
        "/opt/homebrew/bin/adb",
        os.path.expanduser("~/Library/Android/sdk/platform-tools/adb")
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return "adb"

def run_adb_command(command):
    try:
        startupinfo = None
        if platform.system() == "Windows":
            # Hide console window on Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        adb_bin = find_adb()
        result = subprocess.run(
            [adb_bin, "shell"] + command,
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"ADB 명령 실행 실패: {e}")
        return None

def toggle_airplane_mode():
    print("모바일 데이터 비활성화 중 (IP 변경 시작)...")
    # 모바일 데이터 끄기
    run_adb_command(["svc", "data", "disable"])
    
    time.sleep(3)  # IP 갱신 대기
    
    print("모바일 데이터 활성화 중 (네트워크 복구)...")
    # 모바일 데이터 켜기
    run_adb_command(["svc", "data", "enable"])
    
    time.sleep(7)  # 모바일 데이터 재연결 대기
    print("IP 변경 작업 완료")

if __name__ == "__main__":
    toggle_airplane_mode()
