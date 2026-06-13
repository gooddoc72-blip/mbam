import asyncio
from playwright.async_api import async_playwright
import sqlite3
import os
import json
import re

def get_db_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "ranking.db")

async def _scrape_badges_for_keyword(keyword: str, max_scrolls: int = 20):
    """
    Playwright를 사용하여 네이버 지도에서 검색 키워드에 대한 장소 목록의 뱃지(새로오픈, 재방문 많은 등)를 스크래핑합니다.
    """
    print(f"[Deep Crawler] '{keyword}' 플레이스 뱃지 스크래핑 시작...")
    results = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # intercept graphql just in case we need mid mapping
        mids_by_name = {}
        async def handle_response(response):
            if "api/search/allSearch" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    places = data.get("result", {}).get("place", {}).get("list", [])
                    for pl in places:
                        mid = pl.get("id")
                        name = pl.get("name", "")
                        if name.startswith("예약"): name = name.replace("예약", "", 1).strip()
                        if mid and name:
                            mids_by_name[name] = str(mid)
                except Exception:
                    pass
        page.on("response", handle_response)
        
        url = f'https://map.naver.com/p/search/{keyword}'
        print(f"[Deep Crawler] {url} 접속 중...")
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        try:
            frame_element = await page.wait_for_selector('iframe#searchIframe', timeout=10000)
            frame = await frame_element.content_frame()
        except Exception as e:
            print(f"[Deep Crawler] 검색 결과 iframe 로딩 실패: {e}")
            await browser.close()
            return {}
            
        try:
            scroll_container = await frame.wait_for_selector('#_pcmap_list_scroll_container', timeout=5000)
        except Exception:
            print(f"[Deep Crawler] 스크롤 컨테이너를 찾을 수 없습니다.")
            await browser.close()
            return {}
            
        print("[Deep Crawler] 목록 스크롤 다운 시작...")
        last_item_count = 0
        consecutive_same_count = 0
        
        for i in range(max_scrolls):
            await scroll_container.evaluate('el => el.scrollBy(0, 5000)')
            await page.wait_for_timeout(1000)
            
            # 하단 다음 페이지 버튼이 있으면 클릭
            try:
                next_btn = await frame.query_selector('.zRM9F a.eUTV2:not([aria-disabled="true"])')
                if next_btn:
                    # 다음 페이지 아이콘이 오른쪽 화살표 모양인지 확인 (단순 a 태그 목록이므로 aria-hidden 등 구조 파악 필요)
                    # 여기서는 간단히 페이지네이션 처리 대신 스크롤에 집중
                    pass
            except Exception:
                pass
                
            items = await frame.query_selector_all('li')
            current_count = len(items)
            
            if current_count == last_item_count:
                consecutive_same_count += 1
                if consecutive_same_count >= 3:
                    # 더 이상 로딩 안됨, 다음 페이지 클릭 시도
                    pagination_buttons = await frame.query_selector_all('.zRM9F a')
                    clicked_next = False
                    if pagination_buttons:
                        for btn in pagination_buttons:
                            is_hidden = await btn.get_attribute('aria-hidden')
                            btn_text = await btn.inner_text()
                            if is_hidden == 'true' and '다음' in btn_text:
                                await btn.click()
                                await page.wait_for_timeout(2000)
                                consecutive_same_count = 0
                                clicked_next = True
                                break
                    if not clicked_next:
                        break # 진짜 끝
            else:
                consecutive_same_count = 0
                
            last_item_count = current_count
            
        print(f"[Deep Crawler] 스크롤 완료, 총 {last_item_count}개 항목 분석 중...")
        
        items = await frame.query_selector_all('li')
        for item in items:
            try:
                text_content = await item.inner_text()
                if not text_content: continue
                
                # 플레이스 이름 추출 (보통 첫 번째 줄 또는 특정 클래스)
                name_parts = text_content.split('\n')
                name = name_parts[0] if name_parts else "Unknown"
                
                # '예약', '새로오픈' 등이 이름에 섞여 있을 수 있으므로 클렌징
                clean_name = re.sub(r'^(예약|새로오픈)\s*', '', name).strip()
                
                # 뱃지 감지
                is_new = '새로오픈' in text_content
                has_revisit = '재방문 많은' in text_content or '요즘 뜨는' in text_content
                
                # Mid 매칭 시도
                mid = mids_by_name.get(clean_name)
                
                if mid:
                    results[mid] = {
                        "name": clean_name,
                        "is_new": is_new,
                        "has_revisit": has_revisit
                    }
                else:
                    # 이름으로도 저장 (Fallback)
                    results[clean_name] = {
                        "name": clean_name,
                        "is_new": is_new,
                        "has_revisit": has_revisit
                    }
            except Exception:
                pass
                
        await browser.close()
        
    print(f"[Deep Crawler] '{keyword}' 뱃지 데이터 수집 완료. (총 {len(results)}개 매장)")
    return results

def run_deep_crawl_for_keyword(keyword: str, limit: int = 30):
    """
    백그라운드에서 키워드별 상위 업체 뱃지/반응도 데이터를 심층 수집하여 DB에 캐시를 덮어씁니다.
    """
    print(f"\\n{'='*50}")
    print(f"[Deep Crawler Track 2] '{keyword}' 분석 시작")
    print(f"{'='*50}\\n")
    
    # 1. Playwright 크롤링 실행
    try:
        badges_data = asyncio.run(_scrape_badges_for_keyword(keyword))
    except Exception as e:
        print(f"[Deep Crawler Error] 크롤링 실패: {e}")
        return
        
    if not badges_data:
        print("[Deep Crawler] 수집된 데이터가 없습니다.")
        return
        
    # 2. DB 읽어오기 (기존 Track 1 결과에 병합)
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    today_str = asyncio.run(asyncio.sleep(0)) or __import__('datetime').datetime.now().strftime("%Y-%m-%d")
    
    try:
        c.execute("SELECT id, snapshot_json FROM place_rank_history WHERE keyword=? AND date=? ORDER BY id DESC LIMIT 1", (keyword, today_str))
        row = c.fetchone()
        
        if row and row[1]:
            row_id = row[0]
            places_data = json.loads(row[1])
            
            updates_count = 0
            for place in places_data:
                mid = str(place.get("mid"))
                name = place.get("name", "")
                
                # 병합 로직: mid로 먼저 찾고, 없으면 name으로 찾음
                badge_info = badges_data.get(mid) or badges_data.get(name)
                
                if badge_info:
                    # 기존 데이터에 덮어쓰기
                    if badge_info["is_new"] and not place.get("is_new"):
                        place["is_new"] = True
                        updates_count += 1
                        
                    if badge_info["has_revisit"] and not place.get("has_revisit"):
                        place["has_revisit"] = True
                        updates_count += 1
                        
            if updates_count > 0:
                print(f"[Deep Crawler] {updates_count}건의 뱃지 데이터 업데이트됨! DB 갱신 중...")
                
                # N2 점수 재계산 (seo_calculator 활용이 가장 좋으나 여기서는 간단히 가점 부여)
                # 이미 place.py에서 뱃지를 가져와 계산하도록 수정되었으므로, DB만 업데이트해두면 다음 번 조회 시 자동 반영됨!
                
                new_json = json.dumps(places_data, ensure_ascii=False)
                c.execute("UPDATE place_rank_history SET snapshot_json=? WHERE id=?", (new_json, row_id))
                conn.commit()
                print("[Deep Crawler] DB 업데이트 완료! 새로고침 시 뱃지와 가점이 즉시 반영됩니다.")
            else:
                print("[Deep Crawler] 변경된 뱃지 데이터가 없어 업데이트를 스킵합니다.")
                
    except Exception as e:
        print(f"[Deep Crawler DB Error] {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # 단독 테스트용
    run_deep_crawl_for_keyword("광안리맛집")
