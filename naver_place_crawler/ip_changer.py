import subprocess
import time

def run_adb_command(command):
    try:
        # Hide console window on Windows
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(
            ["adb", "shell"] + command,
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
    import platform
    if platform.system() == "Darwin":
        print("Mac 환경에서는 자동 IP 변경을 지원하지 않습니다. 수동으로 IP를 변경해주세요.")
        import time
        time.sleep(5)
        return

    print("비행기 모드 활성화 중 (IP 변경 시작)...")
    # 비행기 모드 켜기 (1)
    run_adb_command(["settings", "put", "global", "airplane_mode_on", "1"])
    run_adb_command(["am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true"])
    
    time.sleep(5)  # IP 갱신 대기
    
    print("비행기 모드 비활성화 중 (네트워크 복구)...")
    # 비행기 모드 끄기 (0)
    run_adb_command(["settings", "put", "global", "airplane_mode_on", "0"])
    run_adb_command(["am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false"])
    
    time.sleep(8)  # 네트워크 완전 연결 대기
    print("IP 변경 작업 완료")

if __name__ == "__main__":
    toggle_airplane_mode()
