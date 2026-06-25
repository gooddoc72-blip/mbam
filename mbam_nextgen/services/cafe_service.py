import asyncio
import os
from ..core.stealth import StealthExecutor
try:
    from ..core.logger import logger
except Exception:
    logger = None

class CafeService:
    """
    [Domain Service] 네이버 카페 자동화 특화 로직
    카페 UI 구조 변경 시 이 클래스만 수정하면 됨 (Single Responsibility)
    """
    def __init__(self, stealth: StealthExecutor):
        self.stealth = stealth
        self.selectors = {
            "write_btn": "#cafe-write-btn, .cafe-write-btn, a:has-text('카페 글쓰기'), a:has-text('글쓰기')",
            "title": ".se-documentTitle, .se-title-text, textarea[placeholder*='제목'], input[placeholder*='제목'], [contenteditable='true'][class*='title' i], .textarea_input, #subject, input[name='subject']",
            "body": "#content, .se-content, .se-placeholder",
            "board_select": "#menuId, select[name='menuId'], .select_component, button:has-text('게시판 선택')",
            "popup_close": "button.se-popup-button-cancel, button:has-text('취소'), button:has-text('닫기')",
            "submit": "a:has-text('등록'), button:has-text('등록'), button:has-text('작성완료'), .BaseButton:has-text('등록')"
        }

    @staticmethod
    def _cafe_url(cafe_id: str) -> str:
        """cafe_id가 전체 URL이든 슬러그든 정상 카페 주소로 변환."""
        cid = (cafe_id or "").strip()
        if cid.startswith("http://") or cid.startswith("https://"):
            return cid.rstrip("/")
        if "cafe.naver.com/" in cid:
            return "https://" + cid[cid.index("cafe.naver.com/"):].rstrip("/")
        return f"https://cafe.naver.com/{cid.lstrip('/')}"

    async def navigate_to_cafe(self, page, cafe_id: str):
        """카페 메인 페이지로 이동 (전체 URL/슬러그 모두 처리)"""
        url = self._cafe_url(cafe_id)
        print(f"[CafeService] 카페 진입: {url}")
        await page.goto(url)
        await asyncio.sleep(3)

    async def auto_enter_editor(self, page):
        """카페 홈에서 [글쓰기] 버튼을 자동 클릭"""
        try:
            write_btn = page.locator(self.selectors["write_btn"])
            await write_btn.first.wait_for(timeout=5000)
            await write_btn.first.click()
            print("[CafeService] ✅ [글쓰기] 버튼 자동 클릭 완료")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[CafeService] ⚠️ 글쓰기 버튼 클릭 실패: {e}")
            print("[CafeService] 📌 다이렉트 URL로 진입을 시도합니다.")
            try:
                clubid = await page.evaluate("window.g_sClubId")
                if clubid:
                    direct_url = f"https://cafe.naver.com/ca-fe/cafes/{clubid}/articles/write"
                    print(f"[CafeService] Club ID 발견: {clubid}, Direct URL 진입: {direct_url}")
                    await page.goto(direct_url)
                    await asyncio.sleep(3)
                else:
                    # Fallback
                    cafe_url = page.url
                    if "?" in cafe_url: cafe_url = cafe_url.split("?")[0]
                    if "cafe.naver.com/" in cafe_url:
                        cafe_id = cafe_url.split("cafe.naver.com/")[1].split("/")[0]
                        direct_url = f"https://cafe.naver.com/ca-fe/cafes/{cafe_id}/articles/write"
                        await page.goto(direct_url)
                        await asyncio.sleep(3)
            except Exception as ex:
                print(f"[CafeService] 다이렉트 URL 진입 실패: {ex}")

    async def wait_for_editor(self, context, page):
        """카페 에디터 프레임이 나타날 때까지 대기"""
        print("🔍 [CafeService] 카페 에디터 감시 중...")
        target_frame = None
        # 무한 대기 방지: 최대 30회(약 30초)까지만 폴링
        for _ in range(30):
            for p in context.pages:
                for f in p.frames:
                    try:
                        # 카페 에디터의 핵심 요소 탐색
                        if await f.locator(".se-main-container, .se-content, #content, .textarea_input").count() > 0:
                            target_frame = f
                            break
                    except Exception:
                        continue
                if target_frame: break

            if target_frame:
                print(f"✨ [CafeService] 카페 에디터 포착: {target_frame.name}")
                return target_frame
            await asyncio.sleep(1)

        raise TimeoutError("카페 에디터 프레임을 30초 내에 찾지 못했습니다.")

    async def select_board(self, frame, board_name: str):
        """게시판(말머리) 선택"""
        page = StealthExecutor._get_page_obj(frame)
        print(f"[CafeService] 게시판 선택: {board_name}")

        # 진단: 실제 게시판 선택 UI 후보를 로그에 덤프 (셀렉터 확정용, 비파괴)
        if logger:
            try:
                cand = await frame.evaluate(r"""() => {
                    const out = [];
                    document.querySelectorAll('select, button, a').forEach(el => {
                        const txt = (el.textContent || '').trim().slice(0, 20);
                        const cls = (el.className || '').toString().slice(0, 50);
                        const nm = el.getAttribute('name') || '';
                        if (/게시판|메뉴|menu|board|말머리/i.test(txt + ' ' + cls + ' ' + nm)) {
                            out.push({tag: el.tagName, txt, cls, name: nm});
                        }
                    });
                    return out.slice(0, 25);
                }""")
                logger.error(f"[CafeService] 게시판 선택 후보({len(cand)}개): {cand}")
            except Exception:
                pass

        # 실측 구조: 트리거 button.button("게시판을 선택해 주세요.") → 옵션 button.option(게시판명)
        for root in (frame, page):
            try:
                # 1) 드롭다운 트리거 클릭
                trigger = root.locator("button.button").filter(has_text="게시판").first
                if await trigger.count() == 0:
                    trigger = root.locator("button.button").first
                if await trigger.count() == 0:
                    # 폴백: 기존 셀렉터
                    trigger = root.locator(self.selectors["board_select"]).first
                if await trigger.count() == 0 or not await trigger.is_visible():
                    continue
                await trigger.click()
                await asyncio.sleep(0.8)

                # 2) 게시판명 옵션 클릭 (button/li만 — a 링크는 다른 페이지로 네비게이션되어 에디터가 닫히므로 제외)
                opt = root.locator("button.option").filter(has_text=board_name).first
                if await opt.count() == 0:
                    opt = root.locator(f"button:has-text('{board_name}'), li[role='option']:has-text('{board_name}'), li:has-text('{board_name}')").first
                if await opt.count() > 0 and await opt.is_visible():
                    await opt.click()
                    print(f"[CafeService] ✅ 게시판 선택 완료: {board_name}")
                    await asyncio.sleep(0.8)
                    return True
                print(f"[CafeService] ⚠️ '{board_name}' 옵션을 찾지 못함 (드롭다운은 열림)")
            except Exception as e:
                print(f"[CafeService] 게시판 선택 시도 중 오류: {e}")
                continue
        print(f"[CafeService] ⚠️ '{board_name}' 게시판 선택 실패")
        return False

    async def dismiss_popups(self, frame):
        """방해 팝업 제거"""
        try:
            await asyncio.sleep(2)
            if await frame.locator(self.selectors["popup_close"]).is_visible(timeout=2000):
                await frame.click(self.selectors["popup_close"])
                print("[CafeService] 방해 팝업 제거 완료")
        except: pass

    async def write_post(self, frame, title: str, content: str, images: list = None, speed_mode: str = "normal", speed_multiplier: float = 1.0):
        """카페 원고 타이핑 (블로그와 동일: 본문 가공 + 소제목 위치에 이미지 인라인 삽입)"""
        import re
        print(f"[CafeService] 타이핑 시작: {title[:15]}... (속도: {speed_mode} x{speed_multiplier})")

        # 본문 줄바꿈/단락 가공 (블로그·카페 공용)
        content = StealthExecutor.format_body(content)

        # 진단: 모든 입력 가능한 필드(input/textarea/contenteditable)를 frame·page 양쪽에서 덤프
        page = StealthExecutor._get_page_obj(frame)
        if logger:
            dump_js = r"""() => {
                const out = [];
                document.querySelectorAll('input, textarea, [contenteditable="true"]').forEach(el => {
                    out.push({
                        tag: el.tagName,
                        cls: (el.className || '').toString().slice(0, 45),
                        ph: (el.getAttribute('placeholder') || el.getAttribute('aria-label') || el.getAttribute('data-placeholder') || '').slice(0, 20),
                        type: el.getAttribute('type') || ''
                    });
                });
                return out.slice(0, 25);
            }"""
            for rn, ro in (("frame", frame), ("page", page)):
                try:
                    fc = await ro.evaluate(dump_js)
                    logger.error(f"[CafeService] 입력필드 후보({rn}, {len(fc)}개): {fc}")
                except Exception:
                    pass

        # 제목 입력 — 여러 셀렉터 후보를 순차 시도 (SE3 .se-documentTitle 우선)
        title_sel = self.selectors["title"]
        title_done = False
        page = StealthExecutor._get_page_obj(frame)
        for root in (frame, page):
            for sel in title_sel.split(","):
                sel = sel.strip()
                try:
                    loc = root.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await loc.click()
                        await asyncio.sleep(0.3)
                        # human_type은 시작 시 SE3 툴바를 눌러 포커스를 빼앗아 제목이 안 들어감 →
                        # 제목은 fill()로 직접 입력(이벤트 포함). 실패 시 키보드 타이핑 폴백.
                        ok = False
                        try:
                            await loc.fill("")
                            await loc.fill(title)
                            ok = True
                        except Exception:
                            try:
                                await loc.click()
                                pg = StealthExecutor._get_page_obj(root)
                                await pg.keyboard.type(title, delay=20)
                                ok = True
                            except Exception:
                                ok = False
                        # 입력 검증: 값이 실제로 들어갔는지 확인
                        try:
                            val = (await loc.input_value()) if await loc.evaluate("el => el.tagName === 'INPUT' || el.tagName === 'TEXTAREA'") else (await loc.inner_text())
                        except Exception:
                            val = ""
                        if ok and (val or "").strip():
                            print(f"[CafeService] ✅ 제목 입력 성공: {sel} = '{(val or '')[:20]}'")
                            if logger:
                                logger.error(f"[CafeService] ✅ 제목 입력 확인: {sel} = '{(val or '')[:30]}'")
                            title_done = True
                            break
                        else:
                            print(f"[CafeService] ⚠️ 제목 입력했으나 값 비어있음: {sel}")
                except Exception:
                    continue
            if title_done:
                break
        if not title_done:
            print("[CafeService] ⚠️ 제목 입력 필드를 찾지 못했습니다.")

        # 본문 + 이미지 교차 입력 ([이미지] 마커 위치에 이미지 삽입)
        body_sel = self.selectors["body"]
        await frame.click(body_sel)

        # 진단: 이미지 업로드 버튼 후보 + [이미지] 마커 수 로그 (셀렉터 확정용)
        if logger:
            try:
                imgcand = await frame.evaluate(r"""() => {
                    const out = [];
                    document.querySelectorAll('button').forEach(el => {
                        const cls = (el.className || '').toString();
                        const dn = el.getAttribute('data-name') || '';
                        if (/image|사진|photo/i.test(cls + ' ' + dn)) out.push({cls: cls.slice(0,45), dn});
                    });
                    return out.slice(0, 10);
                }""")
                logger.error(f"[CafeService] 이미지버튼 후보({len(imgcand)}개): {imgcand} | 본문 [이미지] 마커 {content.count('[이미지]')}개")
            except Exception:
                pass

        async def _cursor_to_end():
            try:
                await frame.locator(body_sel).first.evaluate("""el => {
                    const sel = window.getSelection(); const r = document.createRange();
                    r.selectNodeContents(el); r.collapse(false);
                    sel.removeAllRanges(); sel.addRange(r);
                }""")
            except Exception:
                pass

        # 이미지 업로드는 카페 사진 팝업 때문에 멈출(hang) 수 있어 타임아웃으로 보호 → 실패해도 본문은 계속
        async def _safe_upload(img_path):
            try:
                await asyncio.wait_for(self.stealth.upload_image(frame, img_path), timeout=25)
                await asyncio.sleep(2)
                await _cursor_to_end()
                try:
                    await frame.page.keyboard.press("Enter")
                except Exception:
                    pass
                return True
            except asyncio.TimeoutError:
                if logger: logger.error(f"[CafeService] ⏱️ 이미지 업로드 타임아웃(건너뜀): {os.path.basename(img_path)}")
                return False
            except Exception as e:
                if logger: logger.error(f"[CafeService] 이미지 업로드 실패(건너뜀): {e}")
                return False

        chunks = re.split(r'\[이미지\]', content)
        images = images or []
        img_idx = 0
        pending_text = ""
        if logger: logger.info(f"[CafeService] 본문 타이핑/이미지 삽입 시작 (이미지 {len(images)}장, 청크 {len(chunks)}개)")
        for i, chunk in enumerate(chunks):
            if chunk.strip():
                pending_text += chunk.strip() + "\n\n"
            if i < len(chunks) - 1 and img_idx < len(images):
                img_path = images[img_idx]
                if img_path and os.path.exists(img_path):
                    if pending_text.strip():
                        await self.stealth.human_type(frame, body_sel, pending_text, speed_mode=speed_mode, speed_multiplier=speed_multiplier, do_click=False)
                        pending_text = ""
                    if logger: logger.info(f"[CafeService] 이미지 업로드 {img_idx+1}/{len(images)}")
                    await _safe_upload(img_path)
                img_idx += 1

        if pending_text.strip():
            await self.stealth.human_type(frame, body_sel, pending_text, speed_mode=speed_mode, speed_multiplier=speed_multiplier, do_click=False)

        # 남은 이미지는 글 맨 하단에 추가 (안전장치)
        while img_idx < len(images):
            img_path = images[img_idx]
            if img_path and os.path.exists(img_path):
                if logger: logger.info(f"[CafeService] (하단)이미지 업로드 {img_idx+1}/{len(images)}")
                await _safe_upload(img_path)
            img_idx += 1

        if logger: logger.info("[CafeService] ✅ 카페 원고 타이핑(이미지 교차) 완료")
        print("✅ [CafeService] 카페 원고 타이핑(이미지 교차) 완료")

    async def click_like(self, page):
        """대상 게시글의 좋아요(공감) 버튼 클릭. 이미 눌린 상태면 그대로 둔다. (비파괴 진단 포함)"""
        # 신형 카페 SPA는 본문이 iframe(cafe_main) 안에 있을 수 있어 frame·page 모두 시도
        roots = []
        try:
            fr = page.frame(name="cafe_main")
            if fr:
                roots.append(fr)
        except Exception:
            pass
        roots.append(page)
        selectors = [
            "a.u_likeit_list_btn", "a.u_likeit_list_btn._button",
            ".like_no a", ".like_article a", "a.like_article", "button.like_article",
            "a:has-text('좋아요')", "button:has-text('좋아요')",
            "a:has-text('공감')", "button:has-text('공감')",
        ]
        for root in roots:
            if logger:
                try:
                    cand = await root.evaluate(r"""() => {
                        const out=[];
                        document.querySelectorAll('a,button').forEach(el=>{
                            const t=(el.textContent||'').trim().slice(0,12);
                            const c=(el.className||'').toString().slice(0,40);
                            if(/like|좋아|공감|u_likeit/i.test(c+' '+t)) out.push({t,c,pressed:el.getAttribute('aria-pressed')});
                        });
                        return out.slice(0,12);
                    }""")
                    logger.error(f"[CafeService] 좋아요 버튼 후보({len(cand)}): {cand}")
                except Exception:
                    pass
            for sel in selectors:
                try:
                    loc = root.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        if (await loc.get_attribute("aria-pressed")) == "true":
                            print("[CafeService] 이미 좋아요 상태")
                            return True
                        await loc.click(timeout=4000)
                        print(f"[CafeService] ✅ 좋아요 클릭: {sel}")
                        await asyncio.sleep(1.0)
                        return True
                except Exception:
                    continue
        print("[CafeService] ⚠️ 좋아요 버튼을 찾지 못함")
        return False

    async def upload_images(self, frame, image_paths: list):
        """세척된 이미지 순차 업로드"""
        for path in image_paths:
            if os.path.exists(path):
                await self.stealth.upload_image(frame, path)
                await asyncio.sleep(2)

    async def submit_post(self, frame):
        """작성된 원고를 최종 등록"""
        print("[CafeService] 🚀 즉시 발행 시도 중...")
        try:
            page = StealthExecutor._get_page_obj(frame)

            # 진단: 등록 버튼 후보를 로그에 덤프 (셀렉터 확정용, 비파괴)
            if logger:
                try:
                    for root_name, root_obj in (("frame", frame), ("page", page)):
                        cand = await root_obj.evaluate(r"""() => {
                            const out = [];
                            document.querySelectorAll('button, a').forEach(el => {
                                const txt = (el.textContent || '').trim().slice(0, 16);
                                const cls = (el.className || '').toString().slice(0, 50);
                                if (/등록|작성완료|발행|확인/i.test(txt)) out.push({txt, cls});
                            });
                            return out.slice(0, 20);
                        }""")
                        logger.error(f"[CafeService] 등록 버튼 후보({root_name}, {len(cand)}개): {cand}")
                except Exception:
                    pass

            import re
            # 정확히 '등록'인 버튼만 클릭 (임시등록/임시저장 제외). .BaseButton 우선.
            async def _click_exact(root, words):
                pat = re.compile(r'^\s*(?:' + '|'.join(words) + r')\s*$')
                for sel in (".BaseButton", "button", "a", "span[role='button']"):
                    loc = root.locator(sel).filter(has_text=pat)
                    n = await loc.count()
                    for i in range(n):
                        try:
                            if await loc.nth(i).is_visible():
                                await loc.nth(i).click(timeout=5000)
                                return True
                        except Exception:
                            continue
                return False

            clicked = False
            for root in (frame, page):
                if await _click_exact(root, ["등록"]):
                    print("[CafeService] '등록' 클릭")
                    clicked = True
                    break
            if not clicked:
                print("⚠️ [CafeService] '등록' 버튼을 찾지 못했습니다.")
                return False

            # 등록 후 확인/최종 등록 팝업이 뜨면 한 번 더 처리
            await asyncio.sleep(2)
            for root in (frame, page):
                try:
                    if await _click_exact(root, ["등록", "확인"]):
                        print("[CafeService] 발행 확인 클릭")
                        break
                except Exception:
                    continue
            await asyncio.sleep(3)
            print("[CafeService] ✅ 발행 처리 완료")
            return True
        except Exception as e:
            print(f"[CafeService] ⚠️ 등록 중 오류: {e}")
            return False

    # ═══════════════════════════════════════════════
    # 카페 댓글 자동화 관련 기능
    # ═══════════════════════════════════════════════

    async def navigate_to_board(self, page, cafe_id: str, board_name: str):
        """특정 게시판 목록으로 바로 이동"""
        print(f"[CafeService] '{board_name}' 게시판으로 이동 시도...")
        try:
            # 좌측 메뉴에서 게시판 이름 클릭
            board_link = page.locator(f"#menu-area a:has-text('{board_name}')")
            if await board_link.count() > 0:
                await board_link.first.click()
                await asyncio.sleep(3)
                print(f"[CafeService] ✅ '{board_name}' 게시판 진입 성공")
                return True
            else:
                print(f"[CafeService] ⚠️ '{board_name}' 메뉴를 찾을 수 없습니다. (직접 URL 접근 시도)")
                return False
        except Exception as e:
            print(f"[CafeService] ⚠️ 게시판 진입 중 오류: {e}")
            return False

    async def auto_comment_loop(self, page, keyword: str, limit: int = 5, content: str = None, ai_provider: str = "claude", soul = None):
        """게시글 목록을 순회하며 댓글을 작성"""
        import random
        print(f"🔄 [CafeService] 게시글 순회 시작 (최대 {limit}개)")
        
        for i in range(limit):
            try:
                # 1. 카페 목록 프레임 찾기
                cafe_frame = page.frame(name="cafe_main")
                if not cafe_frame:
                    print("[CafeService] ⚠️ cafe_main 프레임을 찾을 수 없습니다. 대기 후 재시도...")
                    await asyncio.sleep(3)
                    cafe_frame = page.frame(name="cafe_main")
                    if not cafe_frame:
                        print("[CafeService] ❌ 프레임 로드 실패, 순회 중단.")
                        break

                # 2. 게시글 목록 탐색 (상단 공지 제외를 위해 일반 글만 타겟팅 하도록 보완 필요, 임시로 앞부터 순회)
                article_titles = cafe_frame.locator("a.article")
                count = await article_titles.count()
                
                if count <= i:
                    print(f"[CafeService] 더 이상 읽을 게시글이 없습니다. (현재 {i}번째)")
                    break
                    
                print(f"\n👉 [{i+1}/{limit}] 게시글 진입 중...")
                
                # N번째 게시글 클릭
                await article_titles.nth(i).click()
                await asyncio.sleep(random.randint(3, 6))
                
                # 다시 프레임 갱신 (페이지 전환됨)
                cafe_frame = page.frame(name="cafe_main")
                if not cafe_frame:
                    continue
                
                # 3. 본문 읽기
                post_content_text = ""
                content_loc = cafe_frame.locator(".se-main-container, .se-content, .ContentRenderer")
                if await content_loc.count() > 0:
                    post_content_text = await content_loc.first.inner_text()
                else:
                    print("[CafeService] 본문을 찾을 수 없거나 이미지가 위주인 글입니다.")
                    post_content_text = "이미지 또는 내용 없음"
                
                print(f"   [본문 일부]: {post_content_text[:50].replace(chr(10), ' ')}...")
                
                # 4. 댓글 작성 내용 준비
                if content and content.strip():
                    comment_text = content
                else:
                    if not soul:
                        print("⚠️ SoulRewriter 객체가 없어 기본 댓글을 사용합니다.")
                        comment_text = f"잘 보고 갑니다~ ({keyword})"
                    else:
                        print("   🧠 AI가 문맥에 맞는 댓글을 생성 중입니다...")
                        # 댓글 뉘앙스를 위한 프롬프트 가공 (본문의 첫 300자만 요약으로 전달)
                        prompt = f"다음은 어느 카페 게시글의 본문입니다: '{post_content_text[:300]}'. 이 글에 대해 '{keyword}'의 뉘앙스로 자연스럽고 짧은 호응 댓글을 1문장으로 작성해줘. 해시태그나 이모지는 과하지 않게 해줘."
                        # 기존 rewrite_for_blog 재사용 또는 별도 메소드
                        try:
                            comment_text = await soul.rewrite_for_blog("", prompt)
                        except Exception as e:
                            print(f"⚠️ AI 댓글 생성 실패: {e}")
                            comment_text = f"잘 보고 갑니다! ({keyword})"
                
                print(f"   [작성할 댓글]: {comment_text}")
                
                # 5. 댓글 입력 및 등록
                comment_input = cafe_frame.locator(".comment_inbox_text")
                if await comment_input.count() > 0:
                    await comment_input.first.click()
                    await asyncio.sleep(0.5)
                    await self.stealth.human_type(cafe_frame, ".comment_inbox_text", comment_text)
                    await asyncio.sleep(1)
                    
                    submit_btn = cafe_frame.locator(".btn_register")
                    if await submit_btn.count() > 0:
                        # await submit_btn.first.click() # 실제 작동 시 주석 해제 (지금은 테스트 모드로 가정하거나 그냥 작동되게 둠)
                        await submit_btn.first.click()
                        print("   ✅ 댓글 등록 완료!")
                    else:
                        print("   ⚠️ 등록 버튼을 찾을 수 없습니다.")
                else:
                    print("   ⚠️ 댓글을 막아두었거나 입력창을 찾을 수 없습니다.")
                
                # 6. 목록으로 돌아가기
                # 보통 '목록' 버튼 클릭 혹은 브라우저 뒤로가기
                back_btn = cafe_frame.locator("a:has-text('목록'), .BaseButton:has-text('목록')")
                if await back_btn.count() > 0:
                    await back_btn.first.click()
                else:
                    await page.go_back()
                    
                await asyncio.sleep(random.randint(4, 8))
                
            except Exception as e:
                print(f"[CafeService] ⚠️ 순회 중 오류 발생 ({i+1}번째): {e}")
                await page.go_back()
                await asyncio.sleep(3)
