import asyncio
import re
import os
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from mbam_nextgen.services.soul import SoulRewriter

class SeoAnalyzerV2:
    """
    [Domain Service] 상위 1~3위 블로그 정밀 분석 (D.I.A+ 역엔지니어링)
    고객이 지정한 프롬프트를 사용하여 키워드 밀도, LSI, 문서 구조, 경험적 요소를 추출합니다.
    """
    
    def __init__(self):
        self.soul = SoulRewriter()
        
        self.system_prompt = """너는 네이버 검색 엔진 최적화(SEO) 및 D.I.A+ 로직 분석 전문가야. 내가 제공하는 텍스트는 현재 특정 키워드로 네이버 1~3위에 상위노출된 경쟁 블로그 글들이야. 이 글들을 분석해서 아래의 수치화된 기준에 따라 리포트를 작성해 줘.

[분석 및 추출 기준]
- 메인 키워드 및 밀도 파악: 가장 많이 반복된 핵심 키워드 1개를 찾고, 평균 몇 회 반복되었는지 계산해 줘.
- 연관 속성 키워드(LSI) 10개 추출: 메인 키워드 외에 문맥상 함께 쓰인 구체적인 관련 단어, 명사, 전문 용어 10개를 빈도수 순으로 추출해 줘.
- 문서 구조 분석: 소제목(H태그)은 평균 몇 개 사용되었으며, 표나 리스트 형태가 포함되어 있는지 파악해 줘.
- 경험적(D.I.A+) 요소 추출: "내돈내산", "직접 해보니", "단점은" 등 작성자의 1차 경험을 나타내는 주관적인 표현 패턴을 3개 이상 찾아 줘."""

    async def fetch_top_3(self, keyword: str) -> list:
        """플레이스/블로그 탭에서 키워드 검색 후 최상위 3개의 본문을 긁어옵니다."""
        print(f"🔍 [AnalyzerV2] '{keyword}' 상위 3개 블로그 탐색 시작...")
        results = []
        search_url = f"https://m.search.naver.com/search.naver?where=m_blog&query={keyword}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B)")
            page = await context.new_page()
            
            # 불필요한 리소스 차단 (속도 향상)
            await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "media", "font"] else route.continue_())
            
            try:
                await page.goto(search_url, timeout=15000, wait_until="domcontentloaded")
                await page.wait_for_selector('a[href*="blog.naver.com/"]', timeout=5000)
                
                elements = await page.query_selector_all('a[href*="blog.naver.com/"]')
                valid_links = []
                for el in elements:
                    href = await el.get_attribute('href')
                    if href and "blog.naver.com/" in href and "profile" not in href and "clip" not in href:
                        if "m.blog.naver.com" not in href:
                            href = href.replace("blog.naver.com", "m.blog.naver.com")
                        if href not in valid_links:
                            valid_links.append(href)
                            if len(valid_links) == 3:
                                break
                                
                # 3개 링크 병렬 크롤링
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    tasks = [self._scrape_post(session, url) for url in valid_links]
                    scraped_data = await asyncio.gather(*tasks)
                    results = [data for data in scraped_data if data]
                    
            except Exception as e:
                print(f"⚠️ [AnalyzerV2] 검색 실패: {e}")
            finally:
                await browser.close()
                
        return results

    async def _scrape_post(self, session, url: str):
        """단일 블로그 포스트의 텍스트와 이미지 수, 공백 등 통계를 추출합니다."""
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            # 모바일 URL에서 PC URL로 변환하여 구조 단순화
            match = re.search(r'blog\.naver\.com/([^/]+)/(\d+)', url)
            if not match: return None
            blog_id, log_no = match.group(1), match.group(2)
            pc_url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
            
            async with session.get(pc_url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    content_div = soup.select_one('.se-main-container, #postViewArea')
                    if not content_div: return None
                    
                    text = content_div.get_text(separator=' ', strip=True)
                    
                    # 통계 추출 (파이썬 로직)
                    img_count = len(content_div.find_all('img'))
                    total_chars_with_space = len(text)
                    total_chars_no_space = len(text.replace(" ", ""))
                    total_words = len(text.split())
                    
                    return {
                        "url": url,
                        "text": text,
                        "img_count": img_count,
                        "chars_with_space": total_chars_with_space,
                        "chars_no_space": total_chars_no_space,
                        "words": total_words
                    }
        except Exception as e:
            print(f"⚠️ [AnalyzerV2] 포스트 크롤링 실패 ({url}): {e}")
        return None

    async def analyze(self, keyword: str) -> dict:
        """전체 파이프라인: 스크래핑 -> 통계 병합 -> AI 프롬프트 분석 -> 리턴"""
        blogs = await self.fetch_top_3(keyword)
        if not blogs:
            return {"success": False, "error": "상위 블로그를 크롤링할 수 없습니다."}
            
        # 통계 합산 (평균치 계산용)
        total_img = sum(b['img_count'] for b in blogs)
        total_chars_with_space = sum(b['chars_with_space'] for b in blogs)
        total_chars_no_space = sum(b['chars_no_space'] for b in blogs)
        total_words = sum(b['words'] for b in blogs)
        
        num_blogs = len(blogs)
        stats = {
            "avg_img_count": total_img // num_blogs,
            "avg_chars_with_space": total_chars_with_space // num_blogs,
            "avg_chars_no_space": total_chars_no_space // num_blogs,
            "avg_words": total_words // num_blogs
        }
        
        # AI 프롬프트 생성
        combined_text = "\n\n---다음 블로그---\n\n".join([b['text'][:3000] for b in blogs]) # 너무 길면 잘림 방지
        
        prompt = f"{self.system_prompt}\n\n[분석할 텍스트 입력]:\n{combined_text}"
        
        print("🧠 [AnalyzerV2] AI에게 정밀 분석 프롬프트 전송 중...")
        try:
            response_text = await self.soul.generate_content(prompt)
            ai_report = response_text
        except Exception as e:
            import traceback
            traceback.print_exc()
            ai_report = f"가이드라인 생성 실패: {e}"
            
        return {
            "success": True,
            "keyword": keyword,
            "stats": stats,
            "ai_report": ai_report
        }
