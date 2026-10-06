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
        # ⚠ 로그인 버튼 셀렉터는 네이버가 바꾼다. 예전 <button id="log.login"> 은 현재 페이지에
        #   존재하지 않는다(2026-08 확인). 그 상태에서는 아이디·비밀번호는 정상 입력되는데
        #   버튼 클릭에서 30초 타임아웃이 나고 로그인이 안 된다.
        #   지금은 레이아웃 두 벌(column/row)을 넣어두고 하나만 보여주므로 :visible 로 고른다.
        #   (구버전 셀렉터도 뒤에 남겨 예전 페이지에서도 동작하게 둔다)
        self.selectors = {
            "id": "#id",
            "pw": "#pw",
            "login_btn": "#loginBtn_column:visible, #loginBtn_row:visible, "
                         "#log\\.login:visible, .btn_login:visible, button[type=submit]:visible",
            "captcha_img": "#captcha_img, img[src*='captcha']",
            "captcha_input": "#chptcha, #captcha"
        }

    async def _fill_credentials(self, page: Page, account_id: str, account_pw: str):
        """아이디/비밀번호 입력.

        1순위 클립보드 붙여넣기(키 입력 패턴이 남지 않아 자동화 탐지에 덜 걸린다),
        pyperclip 이 없거나 클립보드가 막힌 환경이면 직접 입력으로 넘어간다.
        비밀번호가 비어 있으면 아이디만 채우고 사용자가 창에서 직접 입력하게 둔다.
        """
        use_clipboard = True
        try:
            import pyperclip
        except Exception:
            pyperclip = None
            use_clipboard = False
            print("[Auth] pyperclip 없음 → 직접 입력 방식으로 진행합니다.")

        async def _put(selector: str, value: str):
            if not value:
                return
            await page.click(selector)
            if use_clipboard:
                try:
                    pyperclip.copy(value)
                    await page.keyboard.down('Control')
                    await page.keyboard.press('v')
                    await page.keyboard.up('Control')
                    return
                except Exception as e:
                    print(f"[Auth] 클립보드 입력 실패 → 직접 입력으로 전환: {e}")
            await page.fill(selector, value)

        await _put(self.selectors['id'], account_id)
        await asyncio.sleep(0.5)
        await _put(self.selectors['pw'], account_pw)
        await asyncio.sleep(1)

    async def _ensure_keep_logged_in(self, page: Page, quiet: bool = False) -> bool:
        """'로그인 상태 유지' 를 체크한다. 이미 체크돼 있으면 건드리지 않는다.

        ⚠ 이걸 '자동 로그인 시도 직전'에 한 번만 하면 소용이 없다.
          자동 로그인이 실패하면 네이버가 로그인 폼을 새로 그리고 체크가 풀린다.
          그 상태에서 사용자가 직접 로그인하면 인증 쿠키가 '세션 쿠키'로 발급돼
          브라우저를 닫는 순간 사라진다(= 기기인증을 해도 다음 작업에서 또 로그인).
          그래서 수동 로그인을 기다리는 동안에도 계속 확인해 둔다.
        """
        try:
            keep = page.locator("#loginStay, input[name='nvlong'], #keep, #nvlong").first
            if await keep.count() == 0:
                return False
            if await keep.is_checked():
                return True
            try:
                await keep.check(timeout=3000)
            except Exception:
                await page.locator("label[for='loginStay'], label[for='keep']").first.click(timeout=3000)
            if not quiet:
                print("[Auth] '로그인 상태 유지' 체크 완료")
            return True
        except Exception:
            return False

    async def _has_login_cookie(self, page: Page) -> bool:
        """실제로 네이버 로그인 쿠키가 있는지. 화면(DOM/URL)보다 이쪽이 정확하다."""
        try:
            cookies = await page.context.cookies("https://www.naver.com")
        except Exception:
            return False
        return any(c.get("name") in ("NID_AUT", "NID_SES") and c.get("value") for c in cookies)

    # 로그인 도중 사용자가 직접 풀어야 하는 화면(캡차·2단계 인증·새 기기 확인)의 주소 표식.
    # ⚠ 캡차는 nidlogin.login 이 아니라 nidlogin.rcaptcha 로 뜬다(2026-08 프로필 방문기록 확인).
    #   예전 화면 판정은 '주소에 nidlogin.login 이 없고 로그인 버튼이 없으면 성공' 이라
    #   캡차 화면을 로그인 성공으로 보고 창을 닫아버렸다(= 캡차가 떴다가 곧바로 사라짐).
    _CHALLENGE_MARKERS = ("rcaptcha", "captcha", "otp", "2step", "twostep", "deviceconfirm", "devicecheck")

    def _is_challenge_page(self, page: Page) -> bool:
        url = (page.url or "").lower()
        return any(m in url for m in self._CHALLENGE_MARKERS)

    async def _looks_logged_in_by_screen(self, page: Page) -> bool:
        """쿠키를 못 읽을 때만 쓰는 보조 판정.

        네이버 로그인 도메인(nid.naver.com)에 머무는 동안은 캡차·2단계 인증·기기 확인 중일 수
        있으므로 화면만 보고 성공이라 하지 않는다. 로그인이 끝나면 네이버가 다른 도메인으로 보낸다.
        """
        url = (page.url or "").lower()
        if not url or url.startswith("about:") or "nid.naver.com" in url:
            return False
        return await page.locator(self.selectors['login_btn']).count() == 0

    async def clear_login_cookies(self, page: Page):
        """네이버 인증 쿠키(NID_AUT/NID_SES)만 지운다.

        기기 인증은 '지금 이 창에서 실제로 로그인했는지' 를 쿠키로 판정한다. 영구 프로필에
        예전 쿠키가 남아 있으면 로그인 전부터 성공으로 판정돼 창이 바로 닫히므로, 시작 전에 지운다.
        """
        for name in ("NID_AUT", "NID_SES"):
            try:
                await page.context.clear_cookies(name=name)
            except Exception as e:
                print(f"[Auth] 기존 인증 쿠키({name}) 삭제 실패(계속 진행): {e}")

    async def verify_logged_in(self, page: Page) -> bool:
        """'인증완료' 로 기록하기 직전 최종 확인 — 네이버 메인으로 이동해 인증 쿠키가 살아 있는지 본다.

        네이버는 무효한 인증 쿠키를 받으면 지워버리므로, 이동 후에도 남아 있으면 실제 로그인 상태다.
        """
        try:
            await page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"[Auth] 로그인 최종 확인용 이동 실패(쿠키로만 판정): {e}")
        return await self._has_login_cookie(page)

    async def _register_device_if_asked(self, page: Page) -> bool:
        """로그인 직후 뜨는 '새로운 기기 등록' 화면에서 [등록] 을 누른다.

        ⚠ 이걸 누르지 않으면 네이버가 이 PC 를 신뢰 기기로 기억하지 않는다.
          그러면 기기인증(1회 수동 로그인)을 해도 다음 로그인 때 2단계 인증이 또 뜬다.
          지금까지 이 화면을 아예 처리하지 않아, 매번 2차 인증이 반복됐다.

        버튼은 예전부터 id="new.save"(등록) / id="new.dontsave"(등록안함) 이지만,
        마크업이 바뀔 수 있으므로 역할+정확한 텍스트로도 찾는다.
        '등록안함' 이 '등록' 을 포함하므로 부분일치로 찾으면 안 된다(exact 필수).
        """
        try:
            await asyncio.sleep(1.5)
            url = (page.url or "").lower()
            save = page.locator("#new\\.save").first
            if await save.count() == 0:
                # URL 로도, 기존 버튼으로도 안 잡히면 이 화면이 아닐 가능성이 높다.
                if "deviceconfirm" not in url and "devicecheck" not in url:
                    return False
                save = page.get_by_role("button", name="등록", exact=True).first
                if await save.count() == 0:
                    save = page.get_by_role("link", name="등록", exact=True).first
            if await save.count() == 0:
                print("⚠️ [Auth] '새로운 기기 등록' 화면 같은데 [등록] 버튼을 찾지 못했습니다. 창에서 직접 눌러주세요.")
                return False
            await save.click(timeout=8000)
            await asyncio.sleep(2)
            print("✅ [Auth] 새로운 기기 등록 완료 — 다음 로그인부터 2단계 인증이 반복되지 않습니다.")
            return True
        except Exception as e:
            print(f"[Auth] 기기 등록 처리 중 오류(계속 진행): {e}")
            return False

    async def _click_login(self, page: Page) -> bool:
        """로그인 버튼을 찾아 누른다. 못 찾으면 30초를 버리지 않고 바로 False.

        page.click(selector) 은 요소가 없으면 기본 30초를 기다린 뒤 타임아웃을 낸다.
        네이버가 버튼 마크업을 바꾸면 매 계정마다 30초씩 날아가므로, 먼저 존재를 확인한다.
        """
        try:
            btn = page.locator(self.selectors['login_btn']).first
            if await btn.count() == 0:
                print("❌ [Auth] 로그인 버튼을 찾지 못했습니다. 네이버 로그인 화면이 바뀌었을 수 있습니다.")
                return False
            await btn.click(timeout=10000)
            return True
        except Exception as e:
            print(f"⚠️ [Auth] 로그인 버튼 클릭 실패: {e}")
            return False

    async def login_with_bypass(self, page: Page, account_id: str, account_pw: str, manual_wait_secs: int = 60,
                                fresh_login: bool = False) -> bool:
        """
        네이버 로그인 페이지로 이동하여 로그인 시도.
        캡챠 발생 시 2Captcha를 통해 우회.
        2단계 인증/추가 인증이 뜨면 manual_wait_secs 동안 사용자의 수동 완료를 대기.
        fresh_login=True(기기 인증)면 남아 있던 인증 쿠키를 먼저 지워, 이번 로그인만으로 판정한다.
        """
        pw_len = len(account_pw) if account_pw else 0
        print(f"[Auth] '{account_id}' 자동 로그인 시도 중... (입력된 PW 길이: {pw_len})")
        if pw_len == 0:
            print("❌ [Auth] 비밀번호가 제공되지 않았습니다! (빈 문자열)")
            
        try:
            if fresh_login:
                await self.clear_login_cookies(page)
            await page.bring_to_front()
            await page.goto("https://nid.naver.com/nidlogin.login")
            await asyncio.sleep(2)
            await page.bring_to_front()
            
            # 클립보드 붙여넣기가 가장 덜 잡히지만, pyperclip 이 없는 환경(설치본 등)에서도
            # 로그인 자체는 되어야 한다. 예전에는 여기서 ImportError 가 나면 바깥 except 로
            # 빠져 '수동 로그인 대기'까지 못 가고 브라우저가 즉시 닫혔다.
            await self._fill_credentials(page, account_id, account_pw)

            # "로그인 상태 유지" 체크 → 세션 수명 연장.
            # ⚠ 이게 안 되면 며칠 만에 세션이 만료돼, 기기인증을 해둔 계정도 카페에서
            #   로그아웃 상태가 되고 댓글창이 렌더되지 않는다(실제로 그랬다).
            #   현재 네이버는 #loginStay (name=nvlong) 이고, 예전 #keep/#nvlong 은 존재하지 않는다.
            #   input 이 라벨에 가려 클릭이 막힐 수 있어 check() → 라벨 클릭 순으로 시도한다.
            await self._ensure_keep_logged_in(page)

            # 비밀번호가 없으면 자동 로그인은 애초에 불가능하다. 눌러봐야 에러만 뜨므로
            # 바로 '창에서 직접 로그인' 대기로 넘어간다(기기 인증은 그래도 성립한다).
            if not account_pw:
                print(f"⚠️ [Auth] 저장된 비밀번호가 없습니다. 열린 창에서 직접 로그인해 주세요. ({manual_wait_secs}초 대기)")
                return await self._wait_manual_login(page, manual_wait_secs)

            if not await self._click_login(page):
                print(f"   → 열린 창에서 직접 로그인해 주세요. ({manual_wait_secs}초 대기)")
                return await self._wait_manual_login(page, manual_wait_secs)
            await asyncio.sleep(3)

            # 캡챠 감지 (2Captcha 키가 있는 경우만 자동 풀이 시도)
            if self.api_key and await page.locator(self.selectors['captcha_img']).count() > 0:
                print("⚠️ [Auth] 네이버 캡챠(자동입력방지문자) 감지! 2Captcha API로 자동 풀이 시도...")
                success = await self._solve_captcha(page)
                if success:
                    await self._click_login(page)
                    await asyncio.sleep(3)
                    
            # 로그인 직후 '새로운 기기 등록' 화면이 뜨면 등록해 둔다.
            # (안 하면 다음 로그인 때 2단계 인증이 또 뜬다)
            await self._register_device_if_asked(page)

            # 로그인 성공 여부 확인 — 쿠키가 가장 정확하고, 화면 기준은 보조로만 쓴다.
            if await self._has_login_cookie(page):
                print(f"✅ [Auth] '{account_id}' 자동 로그인 성공! (인증 쿠키 확인)")
                return True
            if await self._looks_logged_in_by_screen(page):
                print(f"✅ [Auth] '{account_id}' 자동 로그인 성공!")
                return True

            # 실패했다면 (비번오류, 캡챠, 2단계 인증 등), 사용자에게 수동 해결 기회 제공
            if self._is_challenge_page(page):
                print(f"⚠️ [Auth] 캡차/2단계 인증 화면이 떴습니다. 창에서 직접 완료해 주세요. ({manual_wait_secs}초 대기)")
            else:
                print(f"⚠️ [Auth] 자동 로그인 실패(또는 캡챠/추가인증 발생). 브라우저 창에서 수동으로 로그인을 완료해 주세요. ({manual_wait_secs}초 대기)")
            try:
                await page.bring_to_front()
            except: pass

            return await self._wait_manual_login(page, manual_wait_secs)

        except Exception as e:
            # 여기까지 왔다는 건 자동 입력 단계에서 문제가 났다는 뜻이다.
            # 그렇다고 창을 바로 닫아버리면 사용자가 직접 로그인할 기회조차 없어진다.
            # (실제로 pyperclip 미설치 때문에 창이 즉시 닫히는 문제가 있었다)
            print(f"⚠️ [Auth] 자동 로그인 과정 중 오류: {e}")
            print(f"   → 열린 창에서 직접 로그인해 주세요. ({manual_wait_secs}초 대기)")
            try:
                return await self._wait_manual_login(page, manual_wait_secs)
            except Exception as e2:
                print(f"❌ [Auth] 수동 로그인 대기도 실패: {e2}")
                return False

    async def _wait_manual_login(self, page: Page, manual_wait_secs: int) -> bool:
        """사용자가 창에서 직접 로그인(캡챠·2단계 인증 포함)을 마칠 때까지 대기."""
        # 창이 어느 화면에서 닫혔는지 알아야 원인을 좁힐 수 있다.
        # (지금까지는 'browser has been closed' 만 찍혀 무엇 때문인지 알 수 없었다)
        try:
            print(f"[Auth] 대기 시작 — 현재 화면: {page.url}")
        except Exception:
            pass
        try:
            page.on("close", lambda _: print("[Auth] ⚠️ 브라우저 '페이지'가 닫혔습니다 (사용자가 창을 닫았거나 크래시)"))
            page.context.on("close", lambda _: print("[Auth] ⚠️ 브라우저 '컨텍스트'가 닫혔습니다 (프로세스 종료)"))
        except Exception:
            pass
        try:
            await page.bring_to_front()
        except Exception:
            pass
        try:
            elapsed = 0
            challenge_notified = False
            for _ in range(max(1, manual_wait_secs // 2)):
                await asyncio.sleep(2)
                elapsed += 2
                if page.is_closed():
                    print(f"[Auth] ❌ {elapsed}초 만에 창이 닫혔습니다. 로그인 완료 전에 창을 닫으면 기기 인증이 저장되지 않습니다.")
                    return False
                if elapsed % 20 == 0:
                    try:
                        print(f"[Auth] …대기 중 {elapsed}/{manual_wait_secs}초 — 현재 화면: {page.url}")
                    except Exception:
                        pass
                # 사용자가 폼을 다시 그릴 때마다 체크가 풀리므로, 제출 전에 계속 확인해 둔다.
                # (이게 빠지면 수동 로그인 쿠키가 세션 쿠키로 발급돼 창을 닫는 순간 사라진다)
                if "nidlogin" in (page.url or ""):
                    await self._ensure_keep_logged_in(page, quiet=True)

                # 1순위: 실제 로그인 쿠키로 판정 (네이버가 화면을 바꿔도 안 깨진다)
                if await self._has_login_cookie(page):
                    print("✅ [Auth] 수동 로그인 완료 감지! (인증 쿠키 확인)")
                    await self._register_device_if_asked(page)
                    return True
                # 캡차·2단계 인증 화면은 사용자가 푸는 중이다 — 성공도 실패도 아니므로 계속 기다린다.
                if self._is_challenge_page(page):
                    if not challenge_notified:
                        print(f"[Auth] 캡차/2단계 인증 화면 감지 — 창에서 직접 완료해 주세요. ({page.url})")
                        challenge_notified = True
                    continue
                # 2순위: 화면 기준 (쿠키를 못 읽는 경우 대비). 네이버 로그인 도메인에 있는 동안은 판정하지 않는다.
                if await self._looks_logged_in_by_screen(page):
                    print("✅ [Auth] 수동 로그인 완료 감지!")
                    # 수동 로그인 뒤에도 '새로운 기기 등록' 화면이 뜬다. 여기서 등록하지 않으면
                    # 기기인증을 했는데도 다음 로그인 때 2단계 인증이 또 뜬다.
                    await self._register_device_if_asked(page)
                    return True
            print(f"❌ [Auth] {manual_wait_secs}초 내에 수동 로그인이 완료되지 않았습니다.")
            return False
        except Exception as e:
            print(f"❌ [Auth] 수동 로그인 대기 중 오류: {e}")
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
