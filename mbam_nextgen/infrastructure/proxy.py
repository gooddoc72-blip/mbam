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
    
    async def rotate_tethering_ip(self) -> str:
        """USB 테더링 IP 변경을 실행하고 변경된 IP 반환"""
        success = await self.tethering.rotate_ip()
        if success:
            new_ip = await self.verify_ip()
            print(f"[ProxyManager] ✅ IP 변경 완료: {new_ip}")
            return new_ip
        return "변경 실패"

    @staticmethod
    def get_random_delay(min_sec: int = 180, max_sec: int = 600) -> int:
        """계정 간 랜덤 대기 시간 생성"""
        return random.randint(min_sec, max_sec)
