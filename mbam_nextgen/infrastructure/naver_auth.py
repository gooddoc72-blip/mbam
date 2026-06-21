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

    async def login_with_bypass(self, page: Page, account_id: str, account_pw: str, manual_wait_secs: int = 60) -> bool:
        """
        네이버 로그인 페이지로 이동하여 로그인 시도.
        캡챠 발생 시 2Captcha를 통해 우회.
        2단계 인증/추가 인증이 뜨면 manual_wait_secs 동안 사용자의 수동 완료를 대기.
        """
        pw_len = len(account_pw) if account_pw else 0
        print(f"[Auth] '{account_id}' 자동 로그인 시도 중... (입력된 PW 길이: {pw_len})")
        if pw_len == 0:
            print("❌ [Auth] 비밀번호가 제공되지 않았습니다! (빈 문자열)")
            
        try:
            await page.bring_to_front()
            await page.goto("https://nid.naver.com/nidlogin.login")
            await asyncio.sleep(2)
            await page.bring_to_front()
            
            import pyperclip
            
            # 클립보드를 이용한 우회 로그인 (가장 안정적)
            await page.click(self.selectors['id'])
            pyperclip.copy(account_id)
            await page.keyboard.down('Control')
            await page.keyboard.press('v')
            await page.keyboard.up('Control')
            await asyncio.sleep(0.5)
            
            await page.click(self.selectors['pw'])
            pyperclip.copy(account_pw)
            await page.keyboard.down('Control')
            await page.keyboard.press('v')
            await page.keyboard.up('Control')
            await asyncio.sleep(1)

            # "로그인 상태 유지" 체크 → 세션 수명 연장 (영구 프로필과 결합 시 2단계 인증 재요구 최소화)
            try:
                keep = page.locator("#keep, .keep_check, label[for='keep'], #nvlong")
                if await keep.count() > 0:
                    await keep.first.click()
                    await asyncio.sleep(0.3)
            except Exception:
                pass

            await page.click(self.selectors['login_btn'])
            await asyncio.sleep(3)
            
            # 캡챠 감지 (2Captcha 키가 있는 경우만 자동 풀이 시도)
            if self.api_key and await page.locator(self.selectors['captcha_img']).count() > 0:
                print("⚠️ [Auth] 네이버 캡챠(자동입력방지문자) 감지! 2Captcha API로 자동 풀이 시도...")
                success = await self._solve_captcha(page)
                if success:
                    await page.click(self.selectors['login_btn'])
                    await asyncio.sleep(3)
                    
            # 로그인 성공 여부 1차 확인 (로그인 버튼 소멸 및 URL 변경)
            if await page.locator(self.selectors['login_btn']).count() == 0 and "nidlogin.login" not in page.url:
                print(f"✅ [Auth] '{account_id}' 자동 로그인 성공!")
                return True
                
            # 실패했다면 (비번오류, 캡챠, 2단계 인증 등), 사용자에게 수동 해결 기회 제공
            print(f"⚠️ [Auth] 자동 로그인 실패(또는 캡챠/추가인증 발생). 브라우저 창에서 수동으로 로그인을 완료해 주세요. ({manual_wait_secs}초 대기)")
            try:
                await page.bring_to_front()
            except: pass

            try:
                for _ in range(max(1, manual_wait_secs // 2)):
                    await asyncio.sleep(2)
                    # 수동으로 로그인하여 로그인 페이지를 벗어났는지 확인
                    if await page.locator(self.selectors['login_btn']).count() == 0 and "nidlogin.login" not in page.url:
                        print("✅ [Auth] 수동 로그인 완료 감지!")
                        return True
                print(f"❌ [Auth] {manual_wait_secs}초 내에 수동 로그인이 완료되지 않았습니다.")
                return False
            except Exception as e:
                print(f"❌ [Auth] 수동 로그인 대기 중 오류: {e}")
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
