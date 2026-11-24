import asyncio
import random
from .tethering import TetheringManager

class ProxyManager:
    """
    [Infrastructure] 프록시 및 테더링 IP 관리 유틸리티
    """
    def __init__(self):
        self.tethering = TetheringManager()
    
    @staticmethod
    def get_browser_proxy_config(proxy_url: str = None) -> dict:
        """Playwright 브라우저 프록시 설정 반환.
        인증형('user:pass@host:port' 또는 'scheme://user:pass@host:port')도 파싱해
        {"server","username","password"} 로 분리한다(Playwright 요구 형식)."""
        if not proxy_url:
            return None
        # 이미 dict(config)로 들어오면 그대로 사용
        if isinstance(proxy_url, dict):
            return proxy_url or None
        try:
            from mbam_nextgen.services.proxy_pool import parse_proxy_line
            cfg = parse_proxy_line(proxy_url)
            if cfg:
                return cfg
        except Exception:
            pass
        # 파싱 실패 시 최소한 server 로라도 전달
        return {"server": proxy_url}
    
    @staticmethod
    async def verify_ip(page=None) -> str:
        """현재 외부 IP 확인 (Playwright 페이지 객체가 있으면 해당 페이지에서, 없으면 직접 요청)"""
        import aiohttp
        try:
            if page:
                await page.goto("https://api.ipify.org?format=text", wait_until="domcontentloaded", timeout=10000)
                ip = await page.inner_text("body")
                return ip.strip()
            else:
                async with aiohttp.ClientSession() as session:
                    async with session.get("https://api.ipify.org?format=text", timeout=5) as resp:
                        return (await resp.text()).strip()
        except:
            return "확인 불가"
    
    async def rotate_tethering_ip_checked(self, attempts: int = 2) -> dict:
        """테더링 IP 를 바꾸고 '실제로 바뀌었는지'까지 확인한다.

        반환: {"ok": bool, "before": str, "after": str, "message": str}
        1.0.3 까지는 명령만 보내고 성공으로 쳐서, 폰이 없거나 명령이 막혀도
        같은 IP 로 다음 계정을 발행했다. 이제는 바뀐 IP 를 눈으로 확인한 경우만 ok.
        """
        from .tethering import find_adb
        if not find_adb():
            return {"ok": False, "before": "", "after": "",
                    "message": "adb 가 없습니다 — [프록시/IP] 화면에서 'adb 내려받기'를 눌러 주세요."}
        try:
            connected, _ = self.tethering.check_device()
        except Exception as e:
            connected = False
        if not connected:
            return {"ok": False, "before": "", "after": "",
                    "message": "연결된 폰이 없습니다 — USB 연결·[USB 디버깅]·'이 컴퓨터 허용'을 확인해 주세요."}
        before = await self.verify_ip()
        after = before
        for n in range(1, attempts + 1):
            if not await self.tethering.rotate_ip():
                return {"ok": False, "before": before, "after": before,
                        "message": "폰이 비행기 모드/데이터 전환 명령을 받지 않았습니다(기종 제한일 수 있음)."}
            # 통신사가 새 IP 를 붙여 주고 테더링이 다시 잡힐 때까지 최대 약 30초 기다린다
            for _ in range(10):
                after = await self.verify_ip()
                if after and after != "확인 불가" and after != before:
                    print(f"[ProxyManager] ✅ IP 변경 완료: {before} → {after}")
                    return {"ok": True, "before": before, "after": after,
                            "message": f"IP 변경: {before} → {after}"}
                await asyncio.sleep(3)
            print(f"[ProxyManager] IP 가 그대로입니다({after}) — 재시도 {n}/{attempts}")
        return {"ok": False, "before": before, "after": after,
                "message": f"IP 가 바뀌지 않았습니다({before} → {after}). 통신사가 같은 IP 를 다시 줬거나 "
                           "테더링이 끊겼을 수 있습니다."}

    async def rotate_tethering_ip(self) -> str:
        """USB 테더링 IP 변경을 실행하고 변경된 IP 반환 (실패 시 '변경 실패')"""
        r = await self.rotate_tethering_ip_checked()
        return r["after"] if r["ok"] else "변경 실패"

    @staticmethod
    def get_random_delay(min_sec: int = 180, max_sec: int = 600) -> int:
        """계정 간 랜덤 대기 시간 생성"""
        return random.randint(min_sec, max_sec)
