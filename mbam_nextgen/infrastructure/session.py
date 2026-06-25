import os
import json
from playwright.async_api import BrowserContext

# 프로필(영구 컨텍스트) 루트 — 계정별 user_data_dir 를 보관
PROFILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles")


def get_profile_dir(account_id: str) -> str:
    """계정 전용 영구 브라우저 프로필 디렉토리 경로 (없으면 생성)."""
    d = os.path.join(PROFILES_DIR, account_id)
    os.makedirs(d, exist_ok=True)
    return d


def _registered_marker(account_id: str) -> str:
    return os.path.join(get_profile_dir(account_id), ".registered")


def is_registered(account_id: str) -> bool:
    """해당 계정이 '기기 인증(1회 수동 로그인)' 을 완료했는지 여부."""
    return os.path.exists(_registered_marker(account_id))


def mark_registered(account_id: str):
    """기기 인증 완료 표시 (영구 프로필이 네이버 신뢰 기기로 등록됨)."""
    try:
        with open(_registered_marker(account_id), "w", encoding="utf-8") as f:
            f.write("ok")
    except Exception:
        pass


def kill_profile_chrome(account_id: str):
    """해당 프로필(user-data-dir)을 점유 중인 잔존 Chrome 프로세스를 강제 종료.
    이전 작업이 비정상 종료되어 좀비 Chrome이 프로필 락을 잡고 있으면,
    새 launch_persistent_context가 즉시 닫힘(Target page closed, exitCode 21)으로 실패하므로 먼저 정리한다."""
    import sys, subprocess
    if sys.platform != "win32":
        return
    d = get_profile_dir(account_id)
    try:
        # 명령줄에 이 프로필 경로가 포함된 chrome.exe만 선별 종료 (다른 계정/일반 크롬은 건드리지 않음)
        out = subprocess.run(
            ["wmic", "process", "where", "name='chrome.exe'", "get", "ProcessId,CommandLine", "/FORMAT:LIST"],
            capture_output=True, text=True, timeout=12, errors="ignore",
        ).stdout or ""
        cmdline = ""
        for raw in out.splitlines():
            line = raw.strip()
            if line.startswith("CommandLine="):
                cmdline = line[len("CommandLine="):]
            elif line.startswith("ProcessId="):
                pid = line[len("ProcessId="):].strip()
                if pid.isdigit() and d in cmdline:
                    subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=6)
                cmdline = ""
    except Exception:
        pass


def clear_stale_locks(account_id: str):
    """
    이전 비정상 종료(서버 강제종료/크래시)로 남은 Chromium 프로필 잠금 + 좀비 Chrome 정리.
    제거하지 않으면 '새 창은 뜨는데 프로필을 못 열어 시작 못함'/'즉시 닫힘(exitCode 21)' 증상이 발생한다.
    한 계정당 한 창만 띄우는 전제로 사용한다.
    """
    kill_profile_chrome(account_id)  # 프로필 점유 중인 좀비 Chrome 먼저 종료
    d = get_profile_dir(account_id)
    for name in ("SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile"):
        try:
            os.remove(os.path.join(d, name))
        except OSError:
            pass


class SessionManager:
    """
    [L4. Stealth - Session Module]
    네이버 로그인 세션을 관리합니다.

    영구 프로필(launch_persistent_context + user_data_dir)을 기본으로 사용하면
    쿠키+localStorage+기기지문이 통째로 유지되어 네이버가 '신뢰 기기'로 기억합니다.
    아래 쿠키 저장/로드는 영구 프로필을 못 쓰는 경로의 하위 호환용으로 남겨둡니다.
    """

    def __init__(self, session_dir: str = None):
        self.session_dir = session_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions"
        )
        if not os.path.exists(self.session_dir):
            os.makedirs(self.session_dir)

    # ---- 영구 프로필 헬퍼 (권장 경로) ----
    def get_profile_dir(self, account_id: str) -> str:
        return get_profile_dir(account_id)

    def is_registered(self, account_id: str) -> bool:
        return is_registered(account_id)

    def mark_registered(self, account_id: str):
        mark_registered(account_id)

    def clear_stale_locks(self, account_id: str):
        clear_stale_locks(account_id)

    # ---- 쿠키 기반 (하위 호환) ----
    def _get_session_path(self, account_id: str):
        return os.path.join(self.session_dir, f"{account_id}_cookies.json")

    async def save_session(self, context: BrowserContext, account_id: str):
        """현재 브라우저의 쿠키 상태를 파일로 저장합니다."""
        try:
            cookies = await context.cookies()
            path = self._get_session_path(account_id)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cookies, f)
            print(f"[Session] '{account_id}' 세션이 저장되었습니다: {path}")
        except Exception as e:
            print(f"[Session] '{account_id}' 세션 저장 실패: {e}")

    async def load_session(self, context: BrowserContext, account_id: str) -> bool:
        """저장된 쿠키를 브라우저에 주입합니다."""
        path = self._get_session_path(account_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                print(f"[Session] '{account_id}' 세션을 성공적으로 로드했습니다.")
                return True
            except Exception as e:
                print(f"[Session] '{account_id}' 세션 로드 실패: {e}")
                return False
        print(f"[Session] '{account_id}' 저장된 세션이 없습니다.")
        return False
