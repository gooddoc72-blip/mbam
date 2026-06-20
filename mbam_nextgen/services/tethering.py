import subprocess
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TetheringController:
    """
    안드로이드 기기를 ADB(Android Debug Bridge)를 통해 제어하여
    비행기 모드를 토글함으로써 통신사 유동 IP를 갱신하는 모듈입니다.
    이 모듈은 '설치형 Premium' 환경에서 USB/테더링으로 연결된 폰에 작동합니다.
    """
    
    def __init__(self):
        self.check_adb_installed()
        
    def check_adb_installed(self):
        try:
            subprocess.run(["adb", "version"], capture_output=True, check=True)
            logger.info("ADB가 정상적으로 설치되어 있습니다.")
        except FileNotFoundError:
            logger.error("ADB(Android Debug Bridge)가 설치되어 있지 않거나 환경 변수에 등록되지 않았습니다.")
            
    def get_connected_devices(self):
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')[1:] # Skip 'List of devices attached'
        devices = [line.split('\t')[0] for line in lines if '\tdevice' in line]
        return devices

    def toggle_airplane_mode(self, device_id=None, delay=3):
        """비행기 모드를 켰다 꺼서 새로운 IP를 발급받습니다."""
        cmd_prefix = ["adb"]
        if device_id:
            cmd_prefix.extend(["-s", device_id])
            
        try:
            logger.info("비행기 모드를 켭니다 (IP 연결 해제)...")
            # 비행기 모드 켜기 (1: Enable, 0: Disable)
            subprocess.run(cmd_prefix + ["shell", "cmd", "connectivity", "airplane-mode", "enable"], check=True)
            time.sleep(delay)
            
            logger.info("비행기 모드를 끕니다 (새로운 IP 할당 요청)...")
            # 비행기 모드 끄기
            subprocess.run(cmd_prefix + ["shell", "cmd", "connectivity", "airplane-mode", "disable"], check=True)
            
            # 통신망(LTE/5G)이 다시 연결될 때까지 충분히 대기
            time.sleep(delay + 2)
            logger.info("테더링 유동 IP 갱신 완료!")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"비행기 모드 제어 실패: {e}")
            return False

if __name__ == "__main__":
    controller = TetheringController()
    devices = controller.get_connected_devices()
    if devices:
        print(f"연결된 기기: {devices[0]}")
        controller.toggle_airplane_mode(devices[0])
    else:
        print("연결된 안드로이드 기기가 없습니다. USB 디버깅을 켜고 연결해주세요.")
