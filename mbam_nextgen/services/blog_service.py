import asyncio
import os
import re
from ..core.stealth import StealthExecutor
from ..core.logger import logger

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

    async def _editor_present(self, page) -> bool:
        """현재 페이지(또는 그 프레임들)에 에디터 본문/제목 필드가 있는지 확인."""
        try:
            for f in page.frames:
                try:
                    if await f.locator(self.selectors["body"]).count() > 0 or await f.locator(self.selectors["title"]).count() > 0:
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    _NON_BLOG_IDS = {"PostList", "PostView", "GoBlogWrite", "PostWriteForm", "MyBlog",
                     "BlogHome", "ThisMonth", "guestbook", "section"}

    async def _discover_real_blog_id(self, page):
        """로그인ID ≠ 블로그주소 계정의 실제 blogId 발견 (다이렉트 URL 재시도용)."""
        try:
            # blog.naver.com 루트는 로그인 사용자의 실제 블로그로 리다이렉트됨
            await page.goto("https://blog.naver.com/", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            m = re.search(r"blog\.naver\.com/([A-Za-z0-9_-]+)(?:[/?#]|$)", page.url)
            if m and m.group(1) not in self._NON_BLOG_IDS:
                return m.group(1)
            # 폴백: 페이지 내 본인 블로그 링크에서 추출
            bid = await page.evaluate(r"""() => {
                const ids = [...document.querySelectorAll('a[href*="blog.naver.com/"]')]
                    .map(x => (String(x.href).match(/blog\.naver\.com\/([A-Za-z0-9_-]+)/) || [])[1])
                    .filter(Boolean);
                return ids[0] || null;
            }""")
            if bid and bid not in self._NON_BLOG_IDS:
                return bid
        except Exception as e:
            logger.info(f"[BlogService] 실제 blogId 발견 실패: {e}")
        return None

    async def auto_enter_editor(self, page, account_id: str, blog_id: str = None):
        """글쓰기 에디터 진입: 다이렉트 URL 시도 → 실패(홈으로 튕김) 시 폴백.
        로그인 ID와 블로그 주소가 다른 계정(예: 로그인 ch_2101 / 블로그 bonetacasa)은
        명시된 blog_id 를 우선 사용하고, 없으면 실제 blogId 자동발견 → '글쓰기' 링크 순으로 폴백한다."""
        try:
            if not account_id:
                logger.info("[BlogService] ⚠️ account_id 없음 — 글쓰기 진입 생략")
                return

            # 명시 블로그 주소(blog_id)가 있으면 그것을, 없으면 로그인 ID를 다이렉트 URL에 사용
            write_id = (blog_id or "").strip() or account_id
            write_url = f"https://blog.naver.com/PostWriteForm.naver?blogId={write_id}"
            logger.info(f"[BlogService] 🚀 다이렉트 글쓰기 URL 이동: {write_url}" + (f" (블로그 주소 지정: {blog_id})" if blog_id else ""))
            await page.goto(write_url, wait_until="domcontentloaded")
            await asyncio.sleep(4)

            if await self._editor_present(page):
                logger.info(f"[BlogService] ✅ ({account_id}) 다이렉트 URL로 에디터 진입 성공 (blogId={write_id})")
                return

            # 1차 폴백: 실제 blogId를 찾아 다이렉트 URL 재시도 → 메인페이지 에디터(mainFrame 경로 회피)
            real_id = await self._discover_real_blog_id(page)
            if real_id and real_id != write_id:
                retry_url = f"https://blog.naver.com/PostWriteForm.naver?blogId={real_id}"
                logger.info(f"[BlogService] 🔁 ({account_id}) 실제 blogId={real_id} 발견 → 다이렉트 재시도: {retry_url}")
                await page.goto(retry_url, wait_until="domcontentloaded")
                await asyncio.sleep(4)
                if await self._editor_present(page):
                    logger.info(f"[BlogService] ✅ ({account_id}) 실제 blogId({real_id}) 다이렉트 진입 성공(메인페이지 에디터)")
                    return

            # 2차 폴백: 블로그 홈의 '글쓰기' 링크 클릭 (GoBlogWrite → mainFrame 경로)
            logger.info(f"[BlogService] ⚠️ ({account_id}) 다이렉트 URL이 에디터 미오픈 → 현재 {page.url} | '글쓰기' 링크 폴백")
            await asyncio.sleep(2)
            href = None
            try:
                href = await page.evaluate(r"""() => {
                    const links = [...document.querySelectorAll('a')];
                    const w = links.find(a => ((a.textContent||'').trim() === '글쓰기')
                        || /postwrite|Redirect=Write|GoBlogWrite|PostWriteForm/i.test(a.getAttribute('href') || a.href || ''));
                    return w ? (w.href || w.getAttribute('href')) : null;
                }""")
            except Exception:
                href = None
            if href:
                logger.info(f"[BlogService] ✅ ({account_id}) '글쓰기' 링크 추출 → 이동: {href}")
                await page.goto(href, wait_until="domcontentloaded")
                await asyncio.sleep(5)
                if await self._editor_present(page):
                    logger.info(f"[BlogService] ✅ ({account_id}) 글쓰기 링크로 에디터 진입 성공")
                    return
            # href 추출 실패 시 클릭 시도 (새 탭으로 열릴 수 있음 → wait_for_editor가 잡음)
            for sel in ["a.btn_write", "a.button_write", "a:has-text('글쓰기')", "button:has-text('글쓰기')",
                        "a[href*='postwrite']", "a[href*='Redirect=Write']", "a[href*='GoBlogWrite']"]:
                try:
                    loc = page.locator(sel)
                    n = await loc.count()
                    for i in range(n):
                        if await loc.nth(i).is_visible():
                            await loc.nth(i).click()
                            logger.info(f"[BlogService] ✅ ({account_id}) '글쓰기' 버튼 클릭 ({sel})")
                            await asyncio.sleep(5)
                            return
                except Exception:
                    continue
            logger.error(f"[BlogService] ⚠️ ({account_id}) '글쓰기' 링크/버튼을 못 찾음 — 현재 페이지: {page.url}")
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

        # 실패 시: 현재 페이지 URL/제목을 로그(mbam_sys.log)에 남기고 스크린샷 저장 → 원인(미개설/보안/추가인증 등) 진단
        try:
            from ..core.logger import logger
        except Exception:
            logger = None
        try:
            info = []
            for idx, p in enumerate(context.pages):
                try:
                    url = p.url
                    title = await p.title()
                    info.append(f"{url} | {title}")
                    try:
                        await p.screenshot(path=f"editor_fail_{idx}.png", full_page=False)
                    except Exception:
                        pass
                except Exception:
                    info.append(getattr(p, 'url', '?'))
            msg = "⚠️ [BlogService] 에디터 미포착. 현재 페이지: " + " || ".join(info) + " (스크린샷: editor_fail_*.png)"
            print(msg)
            if logger:
                logger.error(msg)
        except Exception:
            pass
        raise Exception("블로그 에디터를 찾을 수 없습니다. (블로그 미개설/휴면/보안·추가인증 페이지 가능 — editor_fail_*.png 와 로그 URL 확인)")

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
        """영구 프로필이 기억한 '취소선 ON'을 해제.
        네이버 SE 취소선 버튼: button.se-strikethrough-toolbar-button / [data-name=strikethrough],
        활성 시 class에 'se-is-selected'. 상태 반영이 늦을 수 있어 재시도하며,
        선택돼 있으면 클릭해 끈다(꺼져 있으면 건드리지 않음)."""
        try:
            from ..core.logger import logger
        except Exception:
            logger = None
        JS = r"""() => {
            const sels = ['button.se-strikethrough-toolbar-button',
                          'button[data-name="strikethrough"]',
                          'button[data-log="prt.strike"]'];
            let btn = null;
            for (const s of sels) { const b = document.querySelector(s); if (b) { btn = b; break; } }
            if (!btn) return {found:false};
            const cls = (btn.className || '').toString();
            const selected = /se-is-selected|se-is-on|is-selected|se-is-toggled/.test(cls) || btn.getAttribute('aria-pressed') === 'true';
            let clicked = false;
            if (selected) { try { btn.click(); clicked = true; } catch(e){} }
            return {found:true, selected, clicked, cls};
        }"""
        page = StealthExecutor._get_page_obj(frame)
        try:
            targets = [frame] + [f for f in page.frames if f is not frame]
        except Exception:
            targets = [frame]
        last = None
        # 툴바/선택상태가 늦게 반영될 수 있어 최대 6회(약 3초) 재시도
        for _ in range(6):
            done = False
            for t in targets:
                try:
                    r = await t.evaluate(JS)
                except Exception:
                    continue
                if r and r.get("found"):
                    last = r
                    if r.get("clicked"):
                        print(f"[BlogService] ✅ 취소선 해제 클릭: {r.get('cls')}")
                        done = True
                        break
                    if r.get("found") and not r.get("selected"):
                        done = True  # 이미 꺼져 있음
                        break
            if done:
                break
            await asyncio.sleep(0.5)
        if logger:
            logger.error(f"[BlogService] 취소선 토글 결과: {last}")

    async def _dump_toolbar(self, frame):
        """에디터 툴바 버튼 정보를 로그에 1회 덤프 — 소제목 스타일/글자크기 버튼 셀렉터 확인용(진단)."""
        try:
            from ..core.logger import logger
        except Exception:
            logger = None
        try:
            info = await frame.evaluate(r"""() => {
                const out = [];
                document.querySelectorAll('button').forEach(el => {
                    const cls = (el.className || '').toString();
                    if (!/toolbar/i.test(cls)) return;  // 툴바 버튼만
                    out.push({
                        cls: cls.slice(0, 70),
                        dname: el.getAttribute('data-name') || '',
                        dlog: el.getAttribute('data-log') || '',
                        title: (el.getAttribute('title') || '').slice(0, 16),
                        txt: (el.textContent || '').trim().slice(0, 10)
                    });
                });
                return out;
            }""")
            if logger:
                logger.error(f"[BlogService] 툴바 버튼 덤프({len(info)}개): {info}")

            # 폰트 크기 드롭다운을 열어 옵션 셀렉터를 덤프 (소제목 폰트크기 적용 셀렉터 검증용)
            try:
                fbtn = frame.locator('button[data-name="font-size"]').first
                if await fbtn.count() > 0:
                    await fbtn.click(timeout=2000)
                    await asyncio.sleep(0.4)
                    opts = await frame.evaluate(r"""() => {
                        const out = [];
                        document.querySelectorAll('[class*="option"] button, [class*="option"] li').forEach(el => {
                            const cls = (el.className || '').toString();
                            const txt = (el.textContent || '').trim().slice(0, 6);
                            const dv = el.getAttribute('data-value') || '';
                            if (/font|size|fs/i.test(cls) || /^\d{2}$/.test(txt)) out.push({cls: cls.slice(0,60), txt, dv});
                        });
                        return out;
                    }""")
                    if logger:
                        logger.error(f"[BlogService] 폰트크기 옵션 덤프({len(opts)}개): {opts}")
                    # 드롭다운 닫기
                    try:
                        await frame.page.keyboard.press("Escape")
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            pass

    async def write_post(self, frame, title: str, content: str, images: list = None, speed_mode: str = "normal", speed_multiplier: float = 1.0):
        """원고 타이핑 (스텔스 적용, 속도 조절 가능, 중간 이미지 삽입 지원)"""
        import os, asyncio, re

        # 본문 줄바꿈/단락 가공 (블로그·카페 공용 로직)
        content = StealthExecutor.format_body(content)

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
        # (진단용 _dump_toolbar 제거 — 폰트크기 드롭다운 열고 Escape 누르는 동작이 SE3에서
        #  '작성 취소/나가기'를 유발해 창이 닫히던 원인. 셀렉터(fs16/fs19)는 이미 확보됨)

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
                        await self.stealth.human_type(frame, self.selectors["body"], pending_text, speed_mode=speed_mode, speed_multiplier=speed_multiplier, do_click=False)
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
            await self.stealth.human_type(frame, self.selectors["body"], pending_text, speed_mode=speed_mode, speed_multiplier=speed_multiplier, do_click=False)

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
