import asyncio
import os
from ..core.stealth import StealthExecutor

class CafeService:
    """
    [Domain Service] 네이버 카페 자동화 특화 로직
    카페 UI 구조 변경 시 이 클래스만 수정하면 됨 (Single Responsibility)
    """
    def __init__(self, stealth: StealthExecutor):
        self.stealth = stealth
        self.selectors = {
            "write_btn": "a:has-text('글쓰기'), button:has-text('글쓰기')",
            "title": "#subject, input[name='subject'], .textarea_input",
            "body": "#content, .se-content, .se-placeholder",
            "board_select": "#menuId, select[name='menuId'], .select_component",
            "popup_close": "button.se-popup-button-cancel, button:has-text('취소'), button:has-text('닫기')",
            "submit": "a:has-text('등록'), button:has-text('등록'), button:has-text('작성완료')"
        }

    async def navigate_to_cafe(self, page, cafe_id: str):
        """카페 메인 페이지로 이동"""
        print(f"[CafeService] 카페 진입: {cafe_id}")
        await page.goto(f"https://cafe.naver.com/{cafe_id}")
        await asyncio.sleep(3)

    async def auto_enter_editor(self, page):
        """카페 홈에서 [글쓰기] 버튼을 자동 클릭"""
        try:
            write_btn = page.locator(self.selectors["write_btn"])
            await write_btn.first.wait_for(timeout=10000)
            await write_btn.first.click()
            print("[CafeService] ✅ [글쓰기] 버튼 자동 클릭 완료")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"[CafeService] ⚠️ 글쓰기 버튼 클릭 실패: {e}")
            print("[CafeService] 📌 브라우저에서 직접 [글쓰기]를 눌러주세요.")

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
                        if await f.locator(".se-content, #content, .textarea_input").count() > 0:
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
        
        try:
            # 방법 1: select 드롭다운
            select_el = page.locator(self.selectors["board_select"])
            if await select_el.count() > 0:
                await select_el.first.click()
                await asyncio.sleep(1)
                
                # 게시판 이름으로 옵션 클릭
                option = page.locator(f"option:has-text('{board_name}'), li:has-text('{board_name}'), a:has-text('{board_name}')")
                if await option.count() > 0:
                    await option.first.click()
                    print(f"[CafeService] ✅ 게시판 선택 완료: {board_name}")
                    await asyncio.sleep(1)
                    return True
            
            print(f"[CafeService] ⚠️ '{board_name}' 게시판을 찾을 수 없습니다.")
            return False
            
        except Exception as e:
            print(f"[CafeService] ⚠️ 게시판 선택 중 오류: {e}")
            return False

    async def dismiss_popups(self, frame):
        """방해 팝업 제거"""
        try:
            await asyncio.sleep(2)
            if await frame.locator(self.selectors["popup_close"]).is_visible(timeout=2000):
                await frame.click(self.selectors["popup_close"])
                print("[CafeService] 방해 팝업 제거 완료")
        except: pass

    async def write_post(self, frame, title: str, content: str, speed_mode: str = "normal", speed_multiplier: float = 1.0):
        """카페 원고 타이핑"""
        print(f"[CafeService] 타이핑 시작: {title[:15]}... (속도: {speed_mode} x{speed_multiplier})")
        
        # 제목 입력
        title_sel = self.selectors["title"]
        try:
            await frame.wait_for_selector(title_sel, timeout=10000)
            await frame.click(title_sel)
            await self.stealth.human_type(frame, title_sel, title, speed_mode=speed_mode, speed_multiplier=speed_multiplier)
        except:
            # 제목이 프레임 밖에 있을 수 있음
            page = StealthExecutor._get_page_obj(frame)
            await page.locator(title_sel).first.click()
            await self.stealth.human_type(page, title_sel, title, speed_mode=speed_mode, speed_multiplier=speed_multiplier)
        
        # 본문 입력
        body_sel = self.selectors["body"]
        await frame.click(body_sel)
        await self.stealth.human_type(frame, body_sel, content, speed_mode=speed_mode, speed_multiplier=speed_multiplier)
        print("✅ [CafeService] 카페 원고 타이핑 완료")

    async def upload_images(self, frame, image_paths: list):
        """세척된 이미지 순차 업로드"""
        for path in image_paths:
            if os.path.exists(path):
                await self.stealth.upload_image(frame, path)
                await asyncio.sleep(2)

    async def submit_post(self, frame):
        """글 등록 버튼 클릭"""
        page = StealthExecutor._get_page_obj(frame)
        print("[CafeService] 📝 글 등록 시도 중...")
        
        try:
            submit_btn = frame.locator(self.selectors["submit"])
            if await submit_btn.count() == 0:
                submit_btn = page.locator(self.selectors["submit"])
            
            await submit_btn.first.click()
            await asyncio.sleep(3)
            print("✅ [CafeService] 카페 글 등록 완료!")
            return True
        except Exception as e:
            print(f"⚠️ [CafeService] 글 등록 중 오류: {e}")
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
