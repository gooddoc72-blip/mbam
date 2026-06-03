import os
import asyncio
import base64
from playwright.async_api import Page
import httpx

class NaverAuthenticator:
    """
    [L4. Stealth - Auth Module]
    네이버 로그인 자동화 및 캡챠 우회를 담당합니다.
    (2Captcha API 사용)
    """
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("TWOCAPTCHA_API_KEY", "")
        self.selectors = {
            "id": "#id",
            "pw": "#pw",
            "login_btn": "#log\\.login",
            "captcha_img": "#captcha_img, img[src*='captcha']",
            "captcha_input": "#chptcha, #captcha"
        }

    async def login_with_bypass(self, page: Page, account_id: str, account_pw: str) -> bool:
        """
        네이버 로그인 페이지로 이동하여 로그인 시도.
        캡챠 발생 시 2Captcha를 통해 우회.
        """
        print(f"[Auth] '{account_id}' 자동 로그인 시도 중...")
        try:
            await page.goto("https://nid.naver.com/nidlogin.login")
            await asyncio.sleep(2)
            
            # 클립보드 복사-붙여넣기 방식 (네이버 봇 탐지 우회)
            await page.evaluate(
                "(args) => { document.querySelector(args.idSel).value = args.id; document.querySelector(args.pwSel).value = args.pw; }",
                {"idSel": self.selectors['id'], "id": account_id, "pwSel": self.selectors['pw'], "pw": account_pw}
            )
            await asyncio.sleep(1)
            
            await page.click(self.selectors['login_btn'])
            await asyncio.sleep(3)
            
            # 캡챠 감지
            if await page.locator(self.selectors['captcha_img']).count() > 0:
                print("⚠️ [Auth] 네이버 캡챠(자동입력방지문자) 감지!")
                if not self.api_key:
                    print("❌ [Auth] 2Captcha API 키가 없습니다. 수동으로 캡챠를 풀어주세요.")
                    return False
                    
                success = await self._solve_captcha(page)
                if success:
                    await page.click(self.selectors['login_btn'])
                    await asyncio.sleep(3)
                else:
                    return False
                    
            # 로그인 성공 여부 확인 (내정보 페이지 혹은 로그인 버튼 소멸 확인)
            if await page.locator(self.selectors['login_btn']).count() == 0:
                print(f"✅ [Auth] '{account_id}' 자동 로그인 성공!")
                return True
                
            print(f"❌ [Auth] '{account_id}' 로그인 실패 (비밀번호 오류 또는 추가 인증 필요)")
            return False
            
        except Exception as e:
            print(f"⚠️ [Auth] 로그인 과정 중 오류: {e}")
            return False

    async def _solve_captcha(self, page: Page) -> bool:
        """2Captcha API를 이용하여 이미지 캡챠를 풉니다."""
        print("🔍 [Auth] 2Captcha API로 캡챠 우회 시도 중...")
        try:
            captcha_el = page.locator(self.selectors['captcha_img']).first
            screenshot_bytes = await captcha_el.screenshot()
            b64_image = base64.b64encode(screenshot_bytes).decode('utf-8')
            
            # 1. 2Captcha 서버에 이미지 전송
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.post("https://2captcha.com/in.php", data={
                    "key": self.api_key,
                    "method": "base64",
                    "body": b64_image,
                    "json": 1
                })
                data = res.json()
                
            if data.get("status") != 1:
                print(f"❌ [Auth] 2Captcha 업로드 실패: {data}")
                return False
                
            request_id = data.get("request")
            print(f"⏳ [Auth] 캡챠 해석 대기 중 (ID: {request_id})...")
            
            # 2. 해석 결과 폴링
            for _ in range(15):
                await asyncio.sleep(5)
                async with httpx.AsyncClient(timeout=10) as client:
                    res = await client.get(f"https://2captcha.com/res.php?key={self.api_key}&action=get&id={request_id}&json=1")
                    poll_data = res.json()
                
                if poll_data.get("status") == 1:
                    answer = poll_data.get("request")
                    print(f"💡 [Auth] 캡챠 해답 발견: {answer}")
                    
                    # 캡챠 입력
                    await page.fill(self.selectors['captcha_input'], answer)
                    return True
                elif poll_data.get("request") != "CAPCHA_NOT_READY":
                    print(f"❌ [Auth] 캡챠 풀이 에러: {poll_data}")
                    return False
                    
            print("❌ [Auth] 캡챠 풀이 시간 초과")
            return False
            
        except Exception as e:
            print(f"⚠️ [Auth] 2Captcha 연동 오류: {e}")
            return False
