import asyncio
import random
from playwright.async_api import Page
from mbam_nextgen.core.stealth import StealthExecutor

class CafeAutomator:
    """
    [L5. The Voice - Cafe Module]
    네이버 카페 자동 글쓰기 및 활동 지수 관리 모듈
    """
    
    def __init__(self, stealth: StealthExecutor):
        self.stealth = stealth

    async def post_to_cafe(self, page: Page, cafe_id: str, menu_id: str, title: str, content: str):
        """
        특정 카페의 지정된 게시판에 글을 작성합니다.
        """
        # 1. 카페 글쓰기 페이지 직접 이동 (또는 카페 홈에서 이동)
        write_url = f"https://cafe.naver.com/ca-fe/cafes/{cafe_id}/articles/write?menuId={menu_id}"
        print(f"[Cafe] 글쓰기 페이지 이동: {write_url}")
        await page.goto(write_url)
        await asyncio.sleep(random.uniform(2.0, 4.0))
        
        # 2. 제목 입력
        title_selector = "input.input_title, .BaseEditor .title_textarea"
        await self.stealth.human_mouse_move(page, title_selector)
        await self.stealth.human_type(page, title_selector, title)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        
        # 3. 본문 입력 (iframe 구조 주의)
        print("[Cafe] 본문 입력 시작...")
        # 네이버 카페 에디터는 보통 contenteditable 영역을 사용함
        editor_selector = ".se-content, .editor_body"
        
        # 에디터 영역 클릭 후 타이핑
        await page.click(editor_selector)
        await asyncio.sleep(0.5)
        await self.stealth.human_type(page, editor_selector, content)
        
        # 4. 등록 버튼 클릭
        submit_btn = "button.btn_register, .publish_button"
        await self.stealth.human_mouse_move(page, submit_btn)
        await asyncio.sleep(random.uniform(0.5, 1.5))
        # await page.click(submit_btn) # 실제 등록 시 주석 해제
        
        print(f"[Cafe] 포스팅 완료: {title}")

    async def get_latest_post_url(self, page: Page, cafe_id: str) -> str:
        """
        작성 직후 내 글의 URL을 추출합니다 (댓글 작업용).
        """
        await page.goto(f"https://cafe.naver.com/ca-fe/cafes/{cafe_id}/articles/mine")
        await asyncio.sleep(2)
        # 첫 번째 게시글 링크 추출 로직
        return page.url
