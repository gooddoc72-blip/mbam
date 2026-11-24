"""USB 테더링(안드로이드 폰) — 비행기 모드를 껐다 켜서 통신사 유동 IP 를 새로 받는다.

준비물: 안드로이드 폰 + USB 케이블 + 폰의 [개발자 옵션 > USB 디버깅] + PC 의 adb.

adb 는 설치 파일에 넣지 않는다(안드로이드 SDK 약관상 재배포 제한). 대신
  ① 이미 깔린 adb 를 찾아 쓰고(PATH · 안드로이드 스튜디오 기본 경로 등)
  ② 없으면 [프록시/IP] 화면의 버튼으로 구글 공식 배포본을 사용자 PC 에 내려받는다(download_adb).

1.0.3 까지의 문제
  - adb 를 PATH 에서만 찾아 고객 PC 에서는 늘 '찾을 수 없음' → 조용히 실패하고
    같은 IP 로 계속 발행했다.
  - 'settings put + am broadcast AIRPLANE_MODE' 는 안드로이드 7 이후 일반 앱/셸에서
    막혀(보호된 브로드캐스트) 최신 폰에서는 실제로 비행기 모드가 바뀌지 않았다.
  → 'cmd connectivity airplane-mode'(안드로이드 10+, 루팅 불필요)를 먼저 쓰고,
    안 되면 예전 방식 · 모바일 데이터 껐다 켜기 순으로 시도한다.
  IP 가 실제로 바뀌었는지는 ProxyManager.rotate_tethering_ip_checked 가 확인한다.
"""
import asyncio
import os
import shutil
import subprocess
import sys
from pathlib import Path

# 창 없는 실행(pythonw)에서 adb 를 부를 때마다 검은 콘솔 창이 깜빡이지 않게
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"


def _user_tools_dir() -> Path:
    """download_adb 가 내려받는 위치 (설치 폴더가 아니라 사용자 폴더 — 업데이트·재설치에도 유지)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "MBAM" / "platform-tools"


def find_adb() -> str | None:
    """adb.exe 위치를 찾는다. 없으면 None."""
    cands = []
    if os.environ.get("MBAM_ADB"):
        cands.append(Path(os.environ["MBAM_ADB"]))
    cands.append(_user_tools_dir() / "adb.exe")
    # 설치 폴더(\runtime\adb) — 운영자가 직접 넣어 둔 경우
    app_dir = Path(__file__).resolve().parents[2]
    cands.append(app_dir / "runtime" / "adb" / "adb.exe")
    local = os.environ.get("LOCALAPPDATA")
    if local:
        cands.append(Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe")
    for c in cands:
        if c.is_file():
            return str(c)
    w = shutil.which("adb")
    return w or None


def download_adb(timeout: int = 120) -> str:
    """구글 공식 platform-tools 에서 adb 만 내려받아 사용자 폴더에 둔다. adb 경로를 돌려준다."""
    import io
    import urllib.request
    import zipfile

    dst = _user_tools_dir()
    dst.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(PLATFORM_TOOLS_URL, timeout=timeout) as r:
        data = r.read()
    need = {"adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll"}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            name = info.filename.rsplit("/", 1)[-1]
            if name in need:
                (dst / name).write_bytes(z.read(info))
    adb = dst / "adb.exe"
    if not adb.is_file():
        raise RuntimeError("내려받은 파일에 adb.exe 가 없습니다.")
    return str(adb)


class TetheringManager:
    """[Infrastructure] USB 테더링 및 ADB 기반 IP 로테이션 관리자"""

    def __init__(self, adb_path: str = None):
        # 지정하지 않으면 쓸 때마다 찾는다(실행 중에 adb 를 내려받아도 바로 반영되게)
        self._adb_path = adb_path

    @property
    def adb_path(self) -> str:
        p = self._adb_path or find_adb()
        if not p:
            raise FileNotFoundError("adb 를 찾을 수 없습니다.")
        return p

    def _run(self, *args, timeout: int = 20) -> subprocess.CompletedProcess:
        return subprocess.run([self.adb_path, *args], capture_output=True, text=True,
                              timeout=timeout, creationflags=_NO_WINDOW)

    def check_device(self):
        """연결된 안드로이드 장치가 있는지 확인. (연결여부, 기기목록) 튜플.
        adb 가 없으면 FileNotFoundError 를 그대로 올린다(화면에서 원인을 보여주기 위해)."""
        result = self._run("devices")
        lines = result.stdout.strip().splitlines()
        devices = [ln for ln in lines[1:] if ln.strip().endswith("device")]
        return len(devices) > 0, devices

    def _shell_ok(self, *cmd) -> bool:
        try:
            r = self._run("shell", *cmd)
        except Exception:
            return False
        out = (r.stdout + r.stderr).lower()
        # adb shell 은 원격 명령 실패에도 0 을 돌려주는 기기가 있어 출력으로도 판정한다
        bad = ("exception", "not found", "unknown command", "permission", "error")
        return r.returncode == 0 and not any(b in out for b in bad)

    async def rotate_ip(self) -> bool:
        """비행기 모드(또는 모바일 데이터)를 껐다 켜서 새 IP 를 요청한다.
        명령이 먹혔으면 True. 실제로 IP 가 바뀌었는지는 호출하는 쪽에서 확인한다."""
        print("[Tethering] IP 로테이션 시작...")
        # 1) 안드로이드 10+ 표준 방식 (루팅 불필요)
        if self._shell_ok("cmd", "connectivity", "airplane-mode", "enable"):
            await asyncio.sleep(3)
            self._shell_ok("cmd", "connectivity", "airplane-mode", "disable")
            print("[Tethering] ✈️ 비행기 모드 토글 완료(cmd connectivity)")
            await asyncio.sleep(8)
            return True
        # 2) 예전 방식 (안드로이드 6 이하 또는 일부 제조사)
        if self._shell_ok("settings", "put", "global", "airplane_mode_on", "1"):
            self._shell_ok("am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "true")
            await asyncio.sleep(3)
            self._shell_ok("settings", "put", "global", "airplane_mode_on", "0")
            self._shell_ok("am", "broadcast", "-a", "android.intent.action.AIRPLANE_MODE", "--ez", "state", "false")
            print("[Tethering] ✈️ 비행기 모드 토글 완료(settings)")
            await asyncio.sleep(8)
            return True
        # 3) 모바일 데이터만 껐다 켜기
        if await self.toggle_data():
            print("[Tethering] 📶 모바일 데이터 재연결 완료")
            return True
        print("[Tethering] ❌ 폰이 IP 변경 명령을 받지 않았습니다.")
        return False

    async def toggle_data(self) -> bool:
        """모바일 데이터만 껐다 켜기 (일부 기기에서 작동)"""
        if not self._shell_ok("svc", "data", "disable"):
            return False
        await asyncio.sleep(3)
        self._shell_ok("svc", "data", "enable")
        await asyncio.sleep(8)
        return True
