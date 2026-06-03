import os
import json
from playwright.async_api import BrowserContext

class SessionManager:
    """
    [L4. Stealth - Session Module]
    네이버 로그인 세션(쿠키)을 저장하고 로드하여 자동 로그인을 수행합니다.
    """
    
    def __init__(self, session_dir: str = "mbam_nextgen/sessions"):
        self.session_dir = session_dir
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)

    def _get_session_path(self, account_id: str):
        return os.path.join(self.session_dir, f"{account_id}_cookies.json")

    async def save_session(self, context: BrowserContext, account_id: str):
        """현재 브라우저의 쿠키 상태를 파일로 저장합니다."""
        cookies = await context.cookies()
        path = self._get_session_path(account_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f)
        print(f"[Session] '{account_id}' 세션이 저장되었습니다: {path}")

    async def load_session(self, context: BrowserContext, account_id: str) -> bool:
        """저장된 쿠키를 브라우저에 주입합니다."""
        path = self._get_session_path(account_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print(f"[Session] '{account_id}' 세션을 성공적으로 로드했습니다.")
            return True
        print(f"[Session] '{account_id}' 저장된 세션이 없습니다.")
        return False
