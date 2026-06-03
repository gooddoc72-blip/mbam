import asyncio
from ..core.stealth import StealthExecutor

class NeighborService:
    """
    [Domain Service] 네이버 블로그 이웃추가 및 관리 자동화
    """
    def __init__(self, stealth: StealthExecutor):
        self.stealth = stealth
        self.selectors = {
            "add_btn": "span:has-text('이웃추가'), a:has-text('이웃추가')",
            "mutual_radio": "label:has-text('서로이웃')",
            "message_area": "textarea#buddyAddMessage, .textarea_input",
            "submit_btn": "button:has-text('다음'), button:has-text('확인')"
        }

    async def click_like(self, page):
        """현재 페이지에서 공감 버튼 클릭"""
        try:
            like_btn = page.locator(".u_likeit_list_btn, .btn_sympathy")
            if await like_btn.count() > 0:
                # 이미 클릭되었는지 확인 (보통 aria-pressed나 클래스 변화로 알 수 있음)
                await like_btn.first.click()
                print("[NeighborService] ❤️ 공감 클릭 완료")
                await asyncio.sleep(1)
                return True
        except: pass
        return False

    async def leave_comment(self, page, content: str):
        """현재 페이지에서 댓글 작성"""
        try:
            # 댓글 입력창 찾기 (네이버 블로그 에디터/포스트 구조에 따라 다름)
            comment_area = page.locator(".u_cbox_text, #comment_area, textarea.u_cbox_text")
            if await comment_area.count() > 0:
                await comment_area.first.click()
                await self.stealth.human_type(page, ".u_cbox_text", content, speed_mode="normal")
                
                # 등록 버튼 클릭
                submit_btn = page.locator(".u_cbox_btn_upload, button:has-text('등록')")
                await submit_btn.first.click()
                print(f"[NeighborService] 💬 댓글 작성 완료: {content[:15]}...")
                await asyncio.sleep(2)
                return True
        except Exception as e:
            print(f"[NeighborService] ⚠️ 댓글 작성 실패: {e}")
        return False

    async def add_neighbor(self, page, target_id: str, message: str = "블로그 잘 보고 갑니다! 서로이웃 해요 :)", mutual: bool = True):
        """특정 블로그 이웃 추가 실행"""
        print(f"[NeighborService] 이웃 추가 시도: {target_id}")
        
        # 1. 대상 블로그 프로필 영역으로 이동 (이웃추가 버튼이 있는 곳)
        # 팝업 형태가 아닌 직접 URL 접근이 안정적
        await page.goto(f"https://blog.naver.com/BuddyAddForm.naver?blogId={target_id}")
        await asyncio.sleep(2)
        
        try:
            # 2. 서로이웃 선택 여부
            if mutual:
                mutual_opt = page.locator("input#each_buddy2, label:has-text('서로이웃')")
                if await mutual_opt.count() > 0:
                    await mutual_opt.first.click()
            
            # 3. 신청 메시지 입력
            msg_area = page.locator("textarea#buddyAddMessage")
            if await msg_area.count() > 0:
                await msg_area.first.fill(message)
            
            # 4. 확인 버튼 클릭
            submit = page.locator("a.btn_ok, button:has-text('다음'), button:has-text('확인')")
            await submit.first.click()
            await asyncio.sleep(2)
            
            print(f"✅ [NeighborService] {target_id} 이웃 신청 완료!")
            return True
        except Exception as e:
            print(f"❌ [NeighborService] 이웃 신청 실패: {e}")
            return False

    async def find_targets_from_search(self, page, keyword: str, limit: int = 10):
        """키워드 검색 결과에서 대상 블로그 포스팅 URL 및 ID 추출"""
        print(f"[NeighborService] '{keyword}' 검색 결과에서 대상 추출 중...")
        # 통합 검색의 VIEW 탭으로 이동
        search_url = f"https://search.naver.com/search.naver?where=blog&query={keyword}&sm=tab_opt"
        await page.goto(search_url)
        await asyncio.sleep(2)
        
        # 블로그 포스트 리스트 아이템 추출 (다양한 셀렉터 시도)
        items = await page.locator(".lst_view .bx, li.bx, .total_list .bx").all()
        targets = []
        
        if not items:
            print(f"[NeighborService] ⚠️ '{keyword}'에 대한 검색 결과(li.bx)를 찾지 못했습니다.")
            return []

        for item in items:
            try:
                # 닉네임/ID 링크와 제목 링크 찾기
                name_el = item.locator(".user_info a.name, a.name, .sub_txt.sub_name")
                title_el = item.locator(".title_link, a.api_txt_lines, .total_tit")
                
                if await name_el.count() > 0 and await title_el.count() > 0:
                    href = await name_el.first.get_attribute("href")
                    post_url = await title_el.first.get_attribute("href")
                    
                    if not href or not post_url: continue
                    
                    # ID 추출 로직 개선
                    # https://blog.naver.com/userid 또는 https://blog.naver.com/PostView.naver?blogId=userid...
                    uid = ""
                    if "blog.naver.com/" in href:
                        if "blogId=" in href:
                            import urllib.parse
                            parsed = urllib.parse.urlparse(href)
                            params = urllib.parse.parse_qs(parsed.query)
                            uid = params.get("blogId", [""])[0]
                        else:
                            uid = href.split("/")[-1].split("?")[0]
                    
                    if uid:
                        targets.append({"id": uid, "post_url": post_url})
            except Exception as e: 
                continue
            if len(targets) >= limit: break
            
        print(f"[NeighborService] {len(targets)}개의 대상 포착 완료")
        return targets
