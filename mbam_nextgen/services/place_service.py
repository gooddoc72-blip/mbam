import asyncio
from playwright.async_api import async_playwright
import urllib.parse

class PlaceService:
    """
    [Domain Service] 네이버 스마트플레이스 순위 추적 봇
    특정 키워드로 검색했을 때, 내 매장(상호명)이 몇 위에 노출되는지 파악합니다.
    """
    
    def __init__(self, db_manager=None):
        self.db = db_manager

    async def check_place_rank(self, place_name: str, keyword: str) -> dict:
        """
        네이버 플레이스에서 검색어를 입력하고 상호명이 몇 번째에 있는지 리턴
        """
        print(f"📍 [PlaceService] 플레이스 순위 추적 시작: '{place_name}' (키워드: {keyword})")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True) # 순위 추적은 백그라운드 구동 가능
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                # 네이버 플레이스 검색 URL 구조
                query = urllib.parse.quote(keyword)
                url = f"https://map.naver.com/p/search/{query}"
                await page.goto(url)
                
                # 플레이스 리스트는 보통 searchIframe 안에 있음
                await page.wait_for_selector("iframe#searchIframe", timeout=15000)
                frame_element = await page.query_selector("iframe#searchIframe")
                search_frame = await frame_element.content_frame()
                
                # 로딩 대기
                await asyncio.sleep(3)
                
                # 무한 스크롤 다운을 통해 리스트 전개 (상위 50위 정도까지만 탐색)
                scroll_box_selector = "#_pcmap_list_scroll_container" 
                
                rank = -1
                review_count = 0
                
                # 최대 5페이지(약 50개) 스크롤
                for page_num in range(5):
                    # 현재 화면의 플레이스 아이템들
                    items = await search_frame.locator("li.VLTHu").all() # 네이버 플레이스 리스트 항목 클래스 (자주 변경됨, 보수적 접근 필요)
                    if not items:
                        # 클래스명이 다를 경우를 대비한 폴백 (가게 이름이 들어간 a 태그나 div 찾기)
                        items = await search_frame.locator("li:has(span.YwYLL), li:has(div.TYaxT)").all()
                        
                    for i, item in enumerate(items):
                        text = await item.inner_text()
                        if place_name.replace(" ", "") in text.replace(" ", ""):
                            # 랭크 계산 (현재 스크롤 위치 + 인덱스)
                            rank = i + 1
                            # 리뷰 수 추출 로직 (예: "방문자리뷰 120", "블로그리뷰 50")
                            try:
                                review_text = await item.locator("span:has-text('리뷰')").first.inner_text()
                                # 간단히 숫자만 추출 (추후 정규식으로 고도화)
                                review_count = int(''.join(filter(str.isdigit, review_text)))
                            except:
                                review_count = 0
                                
                            print(f"✅ [PlaceService] '{place_name}' 찾음! 현재 {rank}위 (리뷰: {review_count})")
                            break
                            
                    if rank != -1:
                        break
                        
                    # 스크롤 내리기 로직 구현 생략 (Prototype용: 일단 1페이지 최상위 리스트만 확인)
                    break
                
                if rank == -1:
                    print(f"❌ [PlaceService] 상위 검색 결과에서 '{place_name}'을(를) 찾을 수 없습니다.")
                
                # DB 로깅
                if self.db:
                    self.db.log_place_rank(
                        place_name=place_name,
                        search_keyword=keyword,
                        current_rank=rank,
                        rank_change="-", # 이전 기록과 비교 로직 필요
                        review_count=review_count
                    )
                    
                return {
                    "place_name": place_name,
                    "keyword": keyword,
                    "rank": rank,
                    "review_count": review_count,
                    "success": True
                }

            except Exception as e:
                print(f"⚠️ [PlaceService] 순위 추적 중 오류: {e}")
                return {"place_name": place_name, "success": False, "error": str(e)}
            
            finally:
                await browser.close()
