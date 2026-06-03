import subprocess
import time
import asyncio

class TetheringManager:
    """
    [Infrastructure] USB 테더링 및 ADB 기반 IP 로테이션 관리자
    """
    def __init__(self, adb_path="adb"):
        self.adb_path = adb_path

    def check_device(self):
        """연결된 안드로이드 장치가 있는지 확인"""
        try:
            result = subprocess.run([self.adb_path, "devices"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            devices = [line for line in lines[1:] if line.strip() and 'device' in line and 'devices' not in line]
            return len(devices) > 0, devices
        except Exception as e:
            return False, [str(e)]

    async def rotate_ip(self):
        """비행기 모드 토글을 통해 IP를 강제로 변경 (USB 테더링 환경)"""
        print("[Tethering] IP 로테이션 시작 (비행기 모드 토글)...")
        try:
            # 1. 비행기 모드 ON
            subprocess.run([self.adb_path, "shell", "settings", "put", "global", "airplane_mode_on", "1"], check=True)
            subprocess.run([self.adb_path, "shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true"], check=True)
            print("[Tethering] ✈️ 비행기 모드 ON")
            
            # 2. 대기 (통신사 신호가 끊길 때까지)
            await asyncio.sleep(3)
            
            # 3. 비행기 모드 OFF
            subprocess.run([self.adb_path, "shell", "settings", "put", "global", "airplane_mode_on", "0"], check=True)
            subprocess.run([self.adb_path, "shell", "am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false"], check=True)
            print("[Tethering] ✈️ 비행기 모드 OFF (신호 재잡는 중...)")
            
            # 4. 데이터 연결 및 IP 할당 대기
            await asyncio.sleep(7)
            return True
        except Exception as e:
            print(f"[Tethering] ❌ IP 로테이션 실패: {e}")
            return False

    async def toggle_data(self):
        """모바일 데이터만 껐다 켜기 (일부 기기에서 작동)"""
        try:
            subprocess.run([self.adb_path, "shell", "svc", "data", "disable"], check=True)
            await asyncio.sleep(2)
            subprocess.run([self.adb_path, "shell", "svc", "data", "enable"], check=True)
            await asyncio.sleep(5)
            return True
        except:
            return False
