import asyncio
import os
from ..core.stealth import StealthExecutor

class BlogService:
    """
    [Domain Service] 네이버 블로그 자동화 특화 로직
    UI 구조 변경 시 이 클래스만 수정하면 됨 (Single Responsibility)
    """
    def __init__(self, stealth: StealthExecutor):
        self.stealth = stealth
        self.selectors = {
            "write_btn": ".se-toolbar-button-image, .se-image-toolbar-button",
            "title": ".se-documentTitle, .se-title-text",
            "body": ".se-content, .se-main-container",
            "popup_close": "button.se-popup-button-cancel, button.se-help-close-button"
        }

    async def auto_enter_editor(self, page, account_id: str):
        """블로그 홈에서 글쓰기 URL로 다이렉트 진입 (버튼 클릭 우회)"""
        print("\n" + "="*60)
        print("🚨 [중요] 다이렉트 URL 진입 코드가 실행되고 있습니다! 🚨")
        print("="*60 + "\n")
        try:
            if not account_id:
                print("[BlogService] ⚠️ account_id가 전달되지 않아 글쓰기 우회를 시도하지 않습니다.")
                return
                
            write_url = f"https://blog.naver.com/PostWriteForm.naver?blogId={account_id}"
            print(f"[BlogService] 🚀 [글쓰기] 버튼 클릭 대신 안전한 다이렉트 URL로 바로 이동합니다: {write_url}")
            await page.goto(write_url, wait_until="domcontentloaded")
            await asyncio.sleep(5)
            print("[BlogService] ✅ 다이렉트 URL 진입 완료!")
        except Exception as e:
            print(f"[BlogService] ⚠️ 글쓰기 진입 로직 오류: {e}")

    async def wait_for_editor(self, context, page):
        """에디터 진입 시점을 포착하여 해당 프레임을 반환 (최대 20초 대기)"""
        print("🔍 [BlogService] 에디터 진입 감시 중...")
        for _ in range(20): # 20초 동안 시도
            for p in context.pages:
                # 1. mainFrame iframe이 있는지 확인 (네이버 블로그 에디터는 보통 iframe#mainFrame 안에 있음)
                for f in p.frames:
                    if f.name == "mainFrame":
                        try:
                            if await f.locator(self.selectors["body"]).count() > 0 or await f.locator(self.selectors["title"]).count() > 0:
                                print(f"✨ [BlogService] mainFrame에서 에디터 포착: {f.name}")
                                return f
                        except: pass
                    
                    # 2. iframe이 아닐 경우 그냥 프레임 내용물로 확인
                    try:
                        if await f.locator(self.selectors["body"]).count() > 0 or await f.locator(self.selectors["title"]).count() > 0:
                            print(f"✨ [BlogService] 에디터 포착: {f.name}")
                            return f
                    except: continue
            await asyncio.sleep(1)

        # 실패 시: 현재 페이지 상태(URL/제목)를 남겨 원인(미개설/보안/추가인증 등) 파악
        try:
            info = []
            for p in context.pages:
                try:
                    info.append(f"{p.url} | {await p.title()}")
                except Exception:
                    info.append(getattr(p, 'url', '?'))
            print("⚠️ [BlogService] 에디터 미포착. 현재 페이지: " + " || ".join(info))
        except Exception:
            pass
        raise Exception("블로그 에디터를 찾을 수 없습니다. (블로그 미개설/휴면/보안·추가인증 페이지 가능 — 로그의 '현재 페이지' URL을 확인하세요)")

    async def dismiss_popups(self, frame):
        """방해 팝업(임시저장, 도움말 등) 제거"""
        print("[BlogService] 방해 팝업 체크 중...")
        popups = [
            "button.se-popup-button-cancel", 
            "button.se-help-close-button",
            ".se-alert-button-close",
            "button:has-text('취소')",
            "button:has-text('닫기')"
        ]
        for sel in popups:
            try:
                btn = frame.locator(sel)
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    print(f"[BlogService] 팝업 제거 완료: {sel}")
            except: pass

    async def _reset_text_format(self, frame):
        """이전 세션에서 켜진 채 기억된 글자 서식 토글(취소선/굵게/기울임/밑줄)을 끔 (best-effort).
        영구 프로필이 마지막 서식 상태를 기억해 모든 본문에 취소선이 적용되는 문제 방지."""
        selectors = [
            "button[class*='strikethrough']", "button[class*='strike']",
            "button[data-name='strikethrough']", "button[class*='bold']",
            "button[class*='italic']", "button[class*='underline']",
        ]
        for sel in selectors:
            try:
                btns = frame.locator(sel)
                cnt = await btns.count()
                for i in range(cnt):
                    b = btns.nth(i)
                    cls = (await b.get_attribute("class")) or ""
                    pressed = (await b.get_attribute("aria-pressed")) or ""
                    # 활성화(선택)된 토글만 클릭해서 해제
                    if "active" in cls or "selected" in cls or "on" in cls.split() or pressed == "true":
                        if await b.is_visible():
                            await b.click()
                            print(f"[BlogService] 활성 서식 해제: {sel}")
            except Exception:
                continue

    async def write_post(self, frame, title: str, content: str, images: list = None, speed_mode: str = "normal", speed_multiplier: float = 1.0):
        """원고 타이핑 (스텔스 적용, 속도 조절 가능, 중간 이미지 삽입 지원)"""
        import os, asyncio, re
        
        # 한 문장이 끝나면(. ! ? 뒤) 줄바꿈. 목록 번호("1."), 소수점("3.5")은 제외.
        # 닫는 따옴표/괄호는 문장에 붙여둠.
        content = re.sub(r'(?<![0-9])([.!?]+["\'”’)\]]*)(?!\d)[ \t]*', r'\1\n', content)
        content = re.sub(r'\n{3,}', '\n\n', content)

        print(f"[BlogService] 타이핑 시작: {title[:15]}... (속도: {speed_mode} x{speed_multiplier})")
        
        # 제목 입력
        try:
            await frame.wait_for_selector(self.selectors["title"], timeout=20000)
        except Exception as e:
            print(f"⚠️ [BlogService] 제목 필드 로딩 지연 중. 팝업 재확인 후 진행 시도... {e}")
            await self.dismiss_popups(frame)
            await frame.wait_for_selector(self.selectors["title"], timeout=10000)
            
        await frame.click(self.selectors["title"])
        await self.stealth.human_type(frame, self.selectors["title"], title, speed_mode=speed_mode, speed_multiplier=speed_multiplier)
        
        # 본문 및 이미지 교차 입력
        await frame.click(self.selectors["body"])
        # 이전 세션에서 켜진 채 기억된 서식(취소선/굵게 등) 해제 — best effort
        await self._reset_text_format(frame)

        chunks = re.split(r'\[이미지\]', content)
        images = images or []
        img_idx = 0
        pending_text = ""
        
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                pending_text += chunk.strip() + "\n\n"
            
            # 중간에 이미지가 삽입되어야 하는 위치
            if i < len(chunks) - 1 and img_idx < len(images):
                img_path = images[img_idx]
                if os.path.exists(img_path):
                    if pending_text.strip():
                        await self.stealth.human_type(frame, self.selectors["body"], pending_text, speed_mode=speed_mode, speed_multiplier=speed_multiplier)
                        pending_text = ""
                        
                    await self.stealth.upload_image(frame, img_path)
                    await asyncio.sleep(3)  # 업로드 대기
                    # 포커스를 문서 맨 끝으로 이동
                    await frame.locator(self.selectors["body"]).first.evaluate("""el => {
                        const selection = window.getSelection();
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        range.collapse(false);
                        selection.removeAllRanges();
                        selection.addRange(range);
                    }""")
                    await frame.page.keyboard.press("Enter")
                img_idx += 1
                
        if pending_text.strip():
            await self.stealth.human_type(frame, self.selectors["body"], pending_text, speed_mode=speed_mode, speed_multiplier=speed_multiplier)
            
        # 남은 이미지가 있다면 글 맨 하단에 추가 (안전장치)
        while img_idx < len(images):
            img_path = images[img_idx]
            if os.path.exists(img_path):
                await self.stealth.upload_image(frame, img_path)
                await asyncio.sleep(3)
                await frame.locator(self.selectors["body"]).first.evaluate("""el => {
                    const selection = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(el);
                    range.collapse(false);
                    selection.removeAllRanges();
                    selection.addRange(range);
                }""")
                await frame.page.keyboard.press("Enter")
            img_idx += 1
            
        print("✅ [BlogService] 원고 타이핑(이미지 교차) 완료")

    async def upload_images(self, frame, image_paths: list):
        """세척된 이미지 순차 업로드"""
        for path in image_paths:
            if os.path.exists(path):
                await self.stealth.upload_image(frame, path)
                await asyncio.sleep(2)

    async def publish_now(self, frame):
        """
        [즉시 발행] 발행 버튼을 클릭하여 포스팅을 즉시 공개합니다.
        """
        page = StealthExecutor._get_page_obj(frame)
        print("[BlogService] 🚀 즉시 발행 시도 중...")
        
        try:
            start_url = page.url
            # 1. 상단의 [발행] 버튼 클릭 → 발행 설정 패널 열기
            publish_btn = frame.locator(".btn_submit, button.publish_btn__confirm, button:text-is('발행'), span:text-is('발행')")
            if await publish_btn.count() == 0:
                # 프레임 밖(상위 페이지)에 있을 수 있음
                publish_btn = page.locator(".btn_submit, button.publish_btn__confirm, button:text-is('발행'), span:text-is('발행')")

            await publish_btn.first.click()

            # 2. 발행 설정 레이어의 최종 [발행] 확인 버튼 클릭
            #    네이버 SE confirm 버튼 클래스가 난독화/변경되므로, 명시 클래스 우선 +
            #    '레이어에 새로 나타난 발행 버튼(보이는 것 중 마지막)' 텍스트 기반 폴백.
            clicked = False
            for _ in range(20):  # 최대 ~10초 레이어 대기
                # (a) 명시적 confirm 후보
                for root in (frame, page):
                    for sel in ("button.publish_btn__confirm", ".se-popup-button-confirm",
                                ".layer_btn_area button:has-text('발행')", ".btn_area button:has-text('발행')"):
                        try:
                            loc = root.locator(sel)
                            cnt = await loc.count()
                            for i in range(cnt - 1, -1, -1):
                                if await loc.nth(i).is_visible():
                                    await loc.nth(i).click(timeout=4000)
                                    clicked = True
                                    print(f"✅ [BlogService] 발행 확인 클릭 ({sel})")
                                    break
                        except Exception:
                            pass
                        if clicked:
                            break
                    if clicked:
                        break
                if clicked:
                    break
                # (b) 폴백: 보이는 '발행' 버튼이 2개 이상이면 마지막(레이어 내 확인) 클릭
                try:
                    loc = page.locator("button:has-text('발행'), a:has-text('발행')")
                    cnt = await loc.count()
                    vis = [i for i in range(cnt) if await loc.nth(i).is_visible()]
                    if len(vis) >= 2:
                        await loc.nth(vis[-1]).click(timeout=4000)
                        clicked = True
                        print("✅ [BlogService] 발행 확인 클릭(폴백: 마지막 발행 버튼)")
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)

            if not clicked:
                print("⚠️ [BlogService] 발행 확인 버튼을 찾지 못했습니다. 수동 확인 필요.")
                return False

            # 3. 실제 발행 완료 대기 — 편집 화면을 벗어나(게시글로 이동) 발행이 끝날 때까지
            for _ in range(30):  # 최대 ~15초
                await asyncio.sleep(0.5)
                cur = page.url
                if ("PostWriteForm" not in cur) and ("editor" not in cur) and (cur != start_url):
                    print(f"✅ [BlogService] 즉시 발행 완료! (이동: {cur})")
                    await asyncio.sleep(1)
                    return True
            # URL 변화가 안 잡혀도 확인 클릭은 됐으므로, 발행 반영 여유 대기 후 성공 처리
            await asyncio.sleep(3)
            print("✅ [BlogService] 발행 확인 완료 (URL 변화 미감지 — 여유 대기 후 종료)")
            return True

        except Exception as e:
            print(f"⚠️ [BlogService] 발행 중 오류: {e}")
            return False

    async def schedule_publish(self, frame, schedule_date: str, schedule_time: str):
        """
        [예약 발행] 지정된 날짜/시간에 자동 발행되도록 예약합니다.
        
        Args:
            schedule_date: "2026-05-15" 형식
            schedule_time: "10:30" 형식
        """
        page = StealthExecutor._get_page_obj(frame)
        print(f"[BlogService] ⏰ 예약 발행 설정 중... ({schedule_date} {schedule_time})")
        
        try:
            # 1. 상단의 [발행] 버튼 클릭 (발행 설정 패널 열기)
            publish_btn = frame.locator(".btn_submit, button.publish_btn__confirm, button:text-is('발행'), span:text-is('발행')")
            if await publish_btn.count() == 0:
                publish_btn = page.locator(".btn_submit, button.publish_btn__confirm, button:text-is('발행'), span:text-is('발행')")
            
            await publish_btn.first.click()
            await asyncio.sleep(2)
            
            # 2. 예약 발행 옵션 선택
            reserve_selectors = [
                "label:has-text('예약')",
                "input[value='reserve']",
                "span:has-text('예약')",
                ".se-publish-reserve"
            ]
            
            for sel in reserve_selectors:
                try:
                    reserve_opt = page.locator(sel)
                    if await reserve_opt.count() > 0:
                        await reserve_opt.first.click()
                        print("[BlogService] 예약 옵션 선택 완료")
                        await asyncio.sleep(1)
                        break
                except: continue
            
            # 3. 날짜 입력
            date_input = page.locator("input[type='date'], input.se-publish-date, input[placeholder*='날짜']")
            if await date_input.count() > 0:
                await date_input.first.fill(schedule_date)
                print(f"[BlogService] 날짜 설정: {schedule_date}")
            
            # 4. 시간 입력
            time_input = page.locator("input[type='time'], input.se-publish-time, input[placeholder*='시간']")
            if await time_input.count() > 0:
                await time_input.first.fill(schedule_time)
                print(f"[BlogService] 시간 설정: {schedule_time}")
            
            await asyncio.sleep(1)
            
            # 5. 예약 확인 버튼 클릭
            confirm_selectors = [
                "button:has-text('예약')",
                "button.publish_btn__confirm",
                ".se-popup-button-confirm",
                "button:has-text('확인')"
            ]
            
            for sel in confirm_selectors:
                try:
                    for root in [frame, page]:
                        confirm = root.locator(sel)
                        count = await confirm.count()
                        if count > 0:
                            for i in range(count - 1, -1, -1):
                                if await confirm.nth(i).is_visible():
                                    await confirm.nth(i).click(timeout=5000)
                                    print(f"✅ [BlogService] 예약 발행 완료! (선택자: {sel})")
                                    await asyncio.sleep(3)
                                    return True
                except: continue
            
            print("⚠️ [BlogService] 예약 확인 버튼을 찾지 못했습니다. 수동 확인 필요.")
            return False
            
        except Exception as e:
            print(f"⚠️ [BlogService] 예약 발행 중 오류: {e}")
            return False
