import asyncio
import os
import re
import urllib.parse
from playwright.async_api import async_playwright
import aiohttp
import hmac
import hashlib
import base64
import time

import asyncio
import re
import json
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from mbam_nextgen.services.soul import SoulRewriter

class SeoAnalyzer:
    def __init__(self):
        self.soul = SoulRewriter()

    async def _setup_stealth_page(self, context, block_images: bool = True):
        """페이지 로딩 속도 최적화를 위해 불필요한 리소스(광고 등) 차단.
        block_images=False 시 이미지 로딩을 허용하여 SE3 lazy-load img 카운팅 정확도 확보."""
        page = await context.new_page()
        async def block_aggressively(route):
            blocked = ["media", "font", "stylesheet"]
            if block_images:
                blocked.append("image")
            if route.request.resource_type in blocked:
                await route.abort()
            elif "analytics" in route.request.url or "ads" in route.request.url:
                await route.abort()
            else:
                await route.continue_()

        await page.route("**/*", block_aggressively)
        return page

    async def fetch_top_blogs(self, keyword: str, limit: int = 15, target_urls: list = None) -> tuple:
        """Playwright를 이용해 상위 노출 블로그 본문 스크래핑 (최적화 버전)"""
        
        if target_urls and len(target_urls) > 0:
            print(f"[SEO] '{keyword}' 지정된 {len(target_urls)}개 블로그 분석 시작...")
            links = [{"url": u, "type": "선택된 블로그", "title": "제목 추출 중..."} for u in target_urls]
            smart_blocks = []
        else:
            print(f"[SEO] '{keyword}' 상위 {limit}개 블로그 탐색 시작 (VIEW 기준)...")
            results = []
            # 'm_blog' 대신 최신 스마트블록/VIEW 결과를 반영하는 PC 버전 검색 URL 사용
            search_url = f"https://search.naver.com/search.naver?where=view&query={keyword}"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                page = await self._setup_stealth_page(context)
                
                try:
                    await page.goto(search_url, timeout=15000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                    
                    # 스크롤을 살짝 내려서 동적 로딩 방지
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
                    await page.wait_for_timeout(1000)
                    
                    # 제목을 나타내는 고유 클래스(title_link, total_tit) 추출
                    elements = await page.query_selector_all('a.title_link, a.api_txt_lines.total_tit')
                    valid_links = []
                    
                    for el in elements:
                        href = await el.get_attribute('href')
                        if href and "blog.naver.com/" in href:
                            if not re.search(r'blog\.naver\.com/([^/]+)/(\d+)', href): continue
                            
                            text = await el.inner_text()
                            if not text:
                                text = "제목 없음"
                                
                            post_type = "일반 블로그"
                            # PC 뷰에서는 스마트블록 요소인지 추가로 체크할 수 있지만 기본적으로 검색 노출로 간주
                            if "인플루언서" in text: post_type = "인플루언서"
                            
                            if "m.blog.naver.com" not in href:
                                href = href.replace("blog.naver.com", "m.blog.naver.com")
                                
                            if not any(v['url'] == href for v in valid_links):
                                valid_links.append({"url": href, "type": post_type, "title": text.strip()})
                                if len(valid_links) >= limit:
                                    break
                                
                    links = valid_links[:limit]
                    smart_blocks = await page.evaluate('''() => {
                        const els = document.querySelectorAll('.api_title, .tit_text, .api_subject_bx .tit, .sp_nreview .tit');
                        return Array.from(els).map(el => el.innerText.trim()).filter(t => t.length > 0);
                    }''')
                    smart_blocks = list(set(smart_blocks))
                except Exception as e:
                    print(f"[SEO] 검색 페이지 로딩 실패: {e}")
                    links, smart_blocks = [], []
                finally:
                    await browser.close()
                
        # 2단계: aiohttp 병렬 처리
        import aiohttp
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_post_content(session, idx, item) for idx, item in enumerate(links)]
            fetched_results = await asyncio.gather(*tasks)
            results = [res for res in fetched_results if res]
                        
        return results, smart_blocks

    async def fetch_post_content(self, session, idx, item):
        link = item['url']
        post_type = item['type']
        title = item.get('title', '제목 없음')
        try:
            match = re.search(r'blog\.naver\.com/([^/]+)/(\d+)', link)
            if not match: return None
            blog_id, log_no = match.group(1), match.group(2)
            post_url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with session.get(post_url, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    if title == "제목 추출 중...":
                        title_el = soup.select_one('.se-title-text, .pcol1, .se_title')
                        if title_el:
                            title = title_el.get_text(strip=True)
                        else:
                            title = "제목 없음"

                    content_div = soup.select_one('.se-main-container, #postViewArea')
                    if content_div:
                        text = content_div.get_text(separator=' ', strip=True)
                        return {
                            "rank": idx + 1, "type": post_type, "title": title, "url": link,
                            "text": text, "char_count": len(text.replace(" ", "")),
                            "img_count": len(content_div.find_all('img')),
                            "link_count": len(content_div.find_all('a'))
                        }
        except Exception as e:
            print(f"[SEO] {idx+1}위 추출 실패: {e}")
        return None

    async def extract_keywords_with_ai(self, texts: list, main_keyword: str = "", related_hints: list = None) -> list:
        """검색어(메인 키워드) 컨텍스트를 입힌 의미 연관 서브 키워드 추출.

        반환 형식: [{"keyword": str, "relevance": int(0~100)}, ...]
        count 는 호출부(analyze_keyword)에서 본문 등장 횟수로 별도 계산한다.
        """
        print("[SEO] AI 기반 의미 연관 서브 키워드 추출 중...")

        related_hints = related_hints or []
        combined_text = "\n---\n".join([t[:2000] for t in texts])  # API 제한 고려
        hints_str = ", ".join(related_hints[:8]) if related_hints else "(없음)"

        prompt = f"""당신은 네이버 SEO 키워드 전략가입니다.

[검색 의도]
사용자가 네이버에서 검색한 메인 키워드: "{main_keyword}"
네이버 자동완성 연관어: {hints_str}

[상위 노출 블로그/카페 본문 모음]
{combined_text}

위 본문들에서, 메인 키워드 "{main_keyword}"의 검색 의도와 직접 연관된 "서브 키워드" 20개를 추출하세요.

[추출 기준]
① 메인 키워드와 의미적으로 직접 연관: 하위 카테고리, 동의어, 구체 엔티티(상호/지명/제품명), 지역+업종 결합, 시간/대상/상황 한정어
② 단일 명사보다 2~5어절 복합 명사구 우선 (예: "중앙동 점심", "고등어 솥밥")
③ 네이버 UI/메타 단어 절대 제외 (블로그, 댓글, 본문, 폰트, 사진, 이미지, 작성자, 보기, 카페, 게시글, 이웃 등)
④ 본문에 실제 등장하는 표현만, 가상 단어 금지

[relevance 점수 기준]
- 90~100: 메인 키워드의 구체 하위/엔티티 (검색어 "부산 맛집" → "고등어연구소", "중앙동 솥밥집")
- 70~89 : 메인과 함께 쓰이는 한정어 (예: "혼밥", "점심", "데이트")
- 50~69 : 본문 주제 단어 (느슨한 연관)
- 50 미만: 제외

응답은 다음 JSON 형식으로만 출력 (다른 설명 금지):
{{
  "sub_keywords": [
    {{"keyword": "예시 키워드", "relevance": 85}}
  ]
}}
"""

        try:
            import asyncio
            response_text = await asyncio.wait_for(self.soul.generate_content(prompt), timeout=12.0)
            json_str = re.sub(r'```json\s*|```', '', response_text).strip()
            data = json.loads(json_str)
            raw = data.get("sub_keywords") or data.get("top_keywords") or []  # 구버전 호환
            normalized = []
            for item in raw:
                if isinstance(item, dict) and item.get("keyword"):
                    kw = str(item["keyword"]).strip()
                    if not kw:
                        continue
                    try:
                        rel = int(item.get("relevance", item.get("score", 50)))
                    except (TypeError, ValueError):
                        rel = 50
                    if rel < 50:
                        continue  # 노이즈 컷오프
                    normalized.append({"keyword": kw, "relevance": max(0, min(100, rel))})
            if not normalized:
                raise ValueError("AI가 유효한 서브 키워드를 반환하지 않음")
            return normalized
        except Exception as e:
            print(f"[SEO] AI 키워드 추출 실패: {e}. 파이썬 fallback 사용.")
            return self._fallback_extract_keywords(combined_text, main_keyword, related_hints)

    def _fallback_extract_keywords(self, text: str, main_keyword: str = "", related: list = None) -> list:
        """AI 실패 시 사용. bigram 까지 후보화하고 메인 키워드 토큰/연관어와의 겹침을 가중치로 사용.

        반환 형식: [{"keyword": str, "relevance": int}, ...]
        """
        import collections

        stopwords = {
            "이것", "저것", "그것", "그리고", "그래서", "그러나", "그런데", "하지만",
            "있습니다", "합니다", "하는", "입니다", "있는", "너무", "진짜", "정말",
            "매우", "아주", "많이", "조금", "약간", "그냥", "오늘", "내일", "어제",
            "지금", "가장", "어떤", "이런", "저런", "그런", "다른", "모든", "어떻게",
            "왜", "누구", "어디", "언제", "무엇",
            # 네이버 블로그/카페 UI 단어
            "블로그", "보기", "본문", "폰트", "크기", "댓글", "이웃", "구독",
            "전체보기", "카테고리", "네이버", "공감", "스크랩", "공유", "신고",
            "작성일", "최근", "목록", "더보기", "접기", "펼치기", "서식",
            "이미지", "동영상", "글자", "배경", "색상", "링크", "파일",
            "카페", "게시글", "작성자", "조회", "좋아요", "프로필", "멤버", "닉네임",
        }

        words = re.findall(r'[가-힣A-Za-z]{2,}', text)
        words_f = [w for w in words if w not in stopwords]

        # 2-gram (인접 단어 결합) 후보
        bigrams = [f"{a} {b}" for a, b in zip(words_f, words_f[1:])]

        candidates = collections.Counter(words_f) + collections.Counter(bigrams)

        # 메인 키워드 토큰 / 연관어 set
        main_tokens = set(re.findall(r'[가-힣A-Za-z]{2,}', main_keyword or ""))
        related_set = set(related or [])

        scored = []
        for phrase, cnt in candidates.most_common(300):
            if phrase in stopwords:
                continue
            rel = 50  # 기본
            # 메인 키워드 토큰 직접 포함 시 가중
            if any(tok in phrase for tok in main_tokens):
                rel += 25
            # 네이버 연관어 직접 일치
            if phrase in related_set:
                rel += 25
            # 본문 빈도가 매우 높을수록 약간 보정
            if cnt >= 5:
                rel += 5
            rel = max(0, min(100, rel))
            if rel < 50:
                continue
            scored.append({"keyword": phrase, "relevance": rel, "_count": cnt})

        # 점수 우선, 빈도 보조
        scored.sort(key=lambda x: (x["relevance"], x["_count"]), reverse=True)
        for s in scored:
            s.pop("_count", None)
        return scored[:20]

    async def fetch_related_keywords(self, keyword: str) -> list:
        """네이버 자동완성 API를 사용하여 연관 검색어 추출"""
        import requests
        import asyncio
        url = f"https://ac.search.naver.com/nx/ac?q={keyword}&con=1&rev=4&q_enc=UTF-8&st=100"
        try:
            res = await asyncio.to_thread(requests.get, url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if "items" in data and len(data["items"]) > 0:
                    return [item[0] for item in data["items"][0][:10] if item] # 최대 10개 (빈 항목 IndexError 방지)
        except Exception as e:
            print(f"[SEO] 연관 검색어 추출 실패: {e}")
        return []

    async def fetch_keyword_volumes(self, keywords: list) -> list:
        """네이버 검색광고 API를 사용하여 키워드별 월간 조회수 수집"""
        import time
        import hashlib
        import hmac
        import base64
        import requests
        from dotenv import load_dotenv
        import os

        load_dotenv("mbam_nextgen/.env")
        customer_id = os.getenv("NAVER_CUSTOMER_ID")
        access_license = os.getenv("NAVER_ACCESS_LICENSE")
        secret_key = os.getenv("NAVER_SECRET_KEY")

        if not all([customer_id, access_license, secret_key]):
            print("[SEO] 네이버 광고 API 키가 설정되지 않았습니다.")
            return []

        def generate_signature(timestamp, method, uri, secret):
            message = f"{timestamp}.{method}.{uri}"
            hash = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
            return base64.b64encode(hash.digest()).decode('utf-8')

        method = "GET"
        uri = "/keywordstool"
        import asyncio

        async def fetch_chunk(chunk):
            kw_param = ",".join([k.replace(" ", "") for k in chunk])
            # 타임스탬프/서명은 요청마다 생성 (오래된 타임스탬프 서명 거부 방지)
            timestamp = str(int(time.time() * 1000))
            signature = generate_signature(timestamp, method, uri, secret_key)
            headers = {
                "X-Timestamp": timestamp,
                "X-API-KEY": access_license,
                "X-Customer": str(customer_id),
                "X-Signature": signature
            }
            url = f"https://api.naver.com{uri}"
            try:
                res = await asyncio.to_thread(requests.get, url, params={"hintKeywords": kw_param, "showDetail": 1}, headers=headers, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    chunk_results = []
                    for item in data.get("keywordList", []):
                        def clean_count(c):
                            if isinstance(c, str) and '<' in c: return 10
                            try:
                                return int(str(c).replace(',', '')) if c else 0
                            except (ValueError, TypeError):
                                return 0
                        pc = clean_count(item.get("monthlyPcQcCnt"))
                        mob = clean_count(item.get("monthlyMobileQcCnt"))
                        chunk_results.append({
                            "keyword": item.get("relKeyword"),
                            "pc": pc,
                            "mobile": mob,
                            "total": pc + mob
                        })
                    return chunk_results
                else:
                    print(f"[SEO] API 호출 실패 ({res.status_code}): {res.text}")
                    return []
            except Exception as e:
                print(f"[SEO] 조회수 수집 중 오류: {e}")
                return []
                
        results = []
        chunk_size = 5
        tasks = []
        for i in range(0, len(keywords), chunk_size):
            chunk = keywords[i:i + chunk_size]
            tasks.append(fetch_chunk(chunk))
            
        chunked_results = await asyncio.gather(*tasks)
        for cr in chunked_results:
            results.extend(cr)
        
        return results

    async def analyze_keyword(self, keyword: str, target_urls: list = None) -> dict:
        """키워드 통합 분석 실행 (병렬 처리 최적화 버전)"""
        print(f"[SEO] '{keyword}' 통합 분석 시작 (초고속 모드)...")
        
        if target_urls and len(target_urls) > 0:
            print(f"[SEO] '{keyword}' 지정된 {len(target_urls)}개 블로그 정밀 분석 시작 (Playwright)...")
            # Playwright를 이용해 정밀 스크래핑
            blogs_dict = await self.analyze_multiple_urls(target_urls)
            blogs = []
            for rank, (url, detail) in enumerate(blogs_dict.items()):
                if "error" not in detail:
                    blogs.append({
                        "rank": rank + 1,
                        "type": "인플루언서" if "in.naver.com" in url else "인기카페" if "cafe.naver.com" in url else "인기블로그",
                        "title": detail.get("title", "제목 추출 완료"),
                        "url": url,
                        "blog_id": detail.get("blog_id", ""),
                        "blog_info": detail.get("blog_info", {}),
                        "cafe_author_info": detail.get("cafe_author_info", {}),
                        "text_type": detail.get("text_type", "네이버 블로그"),
                        "source": detail.get("source", "네이버 블로그"),
                        "text": detail.get("full_text", ""),
                        "char_count": detail.get("char_count", 0),
                        "img_count": detail.get("img_count", 0),
                        "link_count": detail.get("link_count", 0),
                        "table_count": detail.get("table_count", 0),
                        "h_tag_count": detail.get("h_tag_count", 0),
                        "rule_properties": detail.get("rule_properties", {})
                    })
            smart_blocks = []
            related = await self.fetch_related_keywords(keyword)
        else:
            # 1단계: 독립적인 작업들 병렬 실행
            fetch_task = self.fetch_top_blogs(keyword, target_urls=None)
            related_task = self.fetch_related_keywords(keyword)
            
            # 병렬 대기 (부분 실패 허용)
            gather_res = await asyncio.gather(fetch_task, related_task, return_exceptions=True)
            blogs_and_smart_blocks = gather_res[0] if not isinstance(gather_res[0], Exception) else ([], [])
            related = gather_res[1] if not isinstance(gather_res[1], Exception) else []
            blogs, smart_blocks = blogs_and_smart_blocks
        
        if not blogs:
            return {"error": "분석할 데이터를 찾지 못했습니다. (접근이 차단되었거나 유효하지 않은 URL일 수 있습니다)"}

        # 2단계: 수집된 블로그/카페 데이터를 바탕으로 AI 분석 (병렬)
        # 1) 메인 키워드 컨텍스트 기반 의미 연관 서브 키워드 추출
        # 2) 메인 + 연관어 검색량 수집
        texts = [b['text'] for b in blogs]
        kw_volumes_task = self.fetch_keyword_volumes([keyword] + related[:4])
        top_kws_task = self.extract_keywords_with_ai(texts, main_keyword=keyword, related_hints=related)

        gather_res2 = await asyncio.gather(kw_volumes_task, top_kws_task, return_exceptions=True)
        kw_volumes = gather_res2[0] if not isinstance(gather_res2[0], Exception) else []
        top_keywords = gather_res2[1] if not isinstance(gather_res2[1], Exception) else []

        # 3단계: 각 서브 키워드에 대해 본문 등장 횟수(count) + 통합 점수(score) 산출
        import math
        vol_map = {v['keyword']: v.get('total', 0) for v in (kw_volumes or [])}

        for kw in top_keywords:
            kw_str = kw['keyword']
            # 모든 블로그 본문 합산 등장 횟수
            kw['count'] = sum(self.count_phrase_occurrences(b.get('text', ''), kw_str) for b in blogs)
            kw['volume'] = vol_map.get(kw_str, 0)
            rel = kw.get('relevance', 50)
            vol_pts = (min(math.log1p(kw['volume']), 12) / 12) * 100  # log scale 0~100
            cnt_pts = (min(kw['count'], 30) / 30) * 100               # 빈도 0~100
            # 통합 점수: 의미 연관 50% + 검색량 30% + 본문 빈도 20%
            kw['score'] = round(rel * 0.5 + vol_pts * 0.3 + cnt_pts * 0.2, 2)

        # 통합 점수 내림차순 정렬
        top_keywords.sort(key=lambda k: k['score'], reverse=True)

        # 4단계: 블로그/카페별 메트릭 + 차별화된 서브 키워드 매핑
        for b in blogs:
            text = b.get('text', '')
            b['char_count_with_spaces'] = len(text)
            b['space_count'] = text.count(" ")
            b['main_kw'] = keyword
            b['main_kw_count'] = self.count_phrase_occurrences(text, keyword)

            # 이 글에서 가장 많이 등장한 "AI 검증 서브 키워드" 1개 → 블로그별 sub_kw
            blog_kw_counts = [
                (kw['keyword'], self.count_phrase_occurrences(text, kw['keyword']))
                for kw in top_keywords[:15]
            ]
            blog_kw_counts.sort(key=lambda x: x[1], reverse=True)

            if blog_kw_counts and blog_kw_counts[0][1] > 0:
                b['sub_kw'] = blog_kw_counts[0][0]
                b['sub_kw_count'] = blog_kw_counts[0][1]
            else:
                b['sub_kw'] = ""
                b['sub_kw_count'] = 0

            # 글별 키워드 분석내역 리스트 (의미 연관 통과 키워드만)
            blog_top_keywords = [
                {"keyword": kw_str, "count": cnt}
                for kw_str, cnt in blog_kw_counts if cnt > 0
            ]
            blog_top_keywords.sort(key=lambda x: x['count'], reverse=True)
            b['top_keywords'] = blog_top_keywords[:20]
        
        # 3단계: 가이드라인 생성
        formula = await self.generate_winning_formula(keyword, blogs, top_keywords)
        
        return {
            "keyword": keyword,
            "metrics": blogs,
            "top_keywords": top_keywords,
            "formula": formula,
            "related": related,
            "smart_blocks": smart_blocks,
            "kw_volumes": kw_volumes
        }
    async def _fetch_blog_tab(self, keyword: str, limit: int = 20) -> list:
        """네이버 통검 '블로그 탭'(ssc=tab.blog.all)에서 블로그 글을 순위 그대로 수집.
        난독화 클래스 대신 'blog.naver.com/{id}/{logNo}' href 패턴으로 추출(클래스 변경에 강함).
        반환: [{title, url, type:'블로그'}] (블로거당 1건, 제목 텍스트 우선)."""
        import urllib.parse
        url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&query={urllib.parse.quote(keyword)}"
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="ko-KR",
                )
                page = await context.new_page()
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    await page.wait_for_timeout(1500)
                    for _ in range(4):
                        await page.evaluate("window.scrollBy(0, 3000)")
                        await page.wait_for_timeout(700)
                    items = await page.evaluate(r"""() => {
                        const rx = /blog\.naver\.com\/([^\/?#]+)\/(\d+)/;
                        const out = [];
                        document.querySelectorAll('a[href]').forEach(a => {
                            const m = a.href.match(rx);
                            if (!m) return;
                            const id = m[1];
                            if (id.endsWith('.naver') || id.includes('.')) return;
                            const txt = (a.innerText || '').trim().replace(/\s+/g, ' ');
                            out.push({ id: id, logno: m[2], txt: txt });
                        });
                        // 제목 텍스트가 있는 링크 우선 → 블로거당 1건 dedup
                        out.sort((a, b) => (b.txt.length > 5 ? 1 : 0) - (a.txt.length > 5 ? 1 : 0));
                        const seen = new Set(); const res = [];
                        for (const o of out) { if (seen.has(o.id)) continue; seen.add(o.id); res.push(o); }
                        return res;
                    }""")
                finally:
                    try:
                        await browser.close()
                    except Exception:
                        pass
            return [{
                "title": (it["txt"][:80] if it.get("txt") else it["id"]),
                "url": f"https://blog.naver.com/{it['id']}/{it['logno']}",
                "type": "블로그",
            } for it in (items or [])[:limit]]
        except Exception as e:
            print(f"[SEO] 블로그 탭 수집 실패: {e}")
            return []

    async def search_smart_blocks(self, keyword: str) -> dict:
        print(f"[SEO] '{keyword}' 스마트블록 탐색 시작...")
        vol_task = asyncio.create_task(self.fetch_keyword_volumes([keyword]))
        search_url = f"https://m.search.naver.com/search.naver?where=m&query={urllib.parse.quote(keyword)}"
        popular_links = []  # '인기글' 블록 전체(블로그+카페+인플) — href 패턴으로 완전 추출

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B)")
            page = await self._setup_stealth_page(context)
            
            try:
                await page.goto(search_url, timeout=15000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1000)
                for _ in range(3):
                    await page.evaluate("window.scrollBy(0, 2000)")
                    await page.wait_for_timeout(400)
                
                blocks = await page.evaluate("""() => {
                    const results = [];
                    const rel_kws = [];
                    
                    // 연관검색어 추출
                    document.querySelectorAll('.related_srch .tit, .lst_related_srch .tit, ._related_keyword_ul li, .api_subject_bx .fds-ugc-block-scroll-list .title, .api_subject_bx .keyword').forEach(el => {
                        let text = el.innerText.trim();
                        if (text && text.length > 1) rel_kws.push(text);
                    });

                    const containers = document.querySelectorAll('section, div.api_subject_bx, .fds-ugc-block, .place_section, .api_custom_bx, .sc_new');
                    const seenBlockHashes = new Set();
                    
                    containers.forEach(container => {
                        let titleEl = container.querySelector('h2, h3, .api_title, .title, .tit, [role="heading"], .subject_title, .api_tit, .place_section_header .name');
                        let blockTitle = titleEl ? titleEl.innerText.trim() : "알 수 없음";
                        
                        if (blockTitle.includes("함께 많이 찾는")) {
                            container.querySelectorAll('a, .title, .tit, .keyword, .name').forEach(el => {
                                let ktext = el.innerText.trim();
                                ktext = ktext.replace(/요즘 인기/g, '').replace(/상승/g, '').split('\\n')[0].trim();
                                if (ktext && ktext.length > 1 && !ktext.includes("함께 많이 찾는") && !/^[0-9 \\/<>\\[\\]]+$/.test(ktext) && ktext !== "이전" && ktext !== "다음") {
                                    rel_kws.push(ktext);
                                }
                            });
                            return;
                        }

                        if (!blockTitle || blockTitle === "알 수 없음" || blockTitle.includes("연관검색어")) return;

                        if (blockTitle !== "새로 오픈" && blockTitle !== "네이버 클립" && !blockTitle.includes("플레이스") && !blockTitle.includes("인플루언서") && !blockTitle.includes("카페") && !blockTitle.includes("블로그") && !blockTitle.includes("새로 오픈") && !blockTitle.includes("업체 등록") && !blockTitle.includes("브랜드 콘텐츠") && !blockTitle.includes("파워링크") && !blockTitle.includes("광고") && blockTitle.length <= 25) {
                            rel_kws.push(blockTitle);
                        }

                        let links = [];
                        let aTags = container.querySelectorAll('a[href]');
                        const seenUrls = new Set();
                        
                        aTags.forEach(a => {
                            let href = a.href;
                            if (!href || href.startsWith('javascript:')) return;
                            if (href.includes('#lb_api')) return;
                            
                            let isAd = a.closest('.sp_power, .powerlink, [class*="ad_"], .sponsored, .ad');
                            if (isAd) return;
                            
                            let titleEl = a.querySelector('.YwYwt, .place_bluelink, .name, .tit, .title, .Fc1rA');
                            let title = "";
                            if (titleEl) {
                                title = titleEl.innerText.trim().replace(/[\\r\\n]+/g, ' ');
                            } else {
                                title = a.innerText.trim().replace(/[\\r\\n]+/g, ' ');
                            }
                            if (!title) return;

                            if (href.includes("m.search.naver.com/search.naver") && href.includes("url=")) {
                                try {
                                    let urlObj = new URL(href);
                                    let realUrl = urlObj.searchParams.get("url");
                                    if (realUrl) href = decodeURIComponent(realUrl);
                                } catch (e) {}
                            }
                            

                            if (a.dataset && a.dataset.url) {
                                href = a.dataset.url;
                            }
                            
                            try {
                                let urlObj = new URL(href);
                                if (href.includes('blog.naver.com')) {
                                    if (!urlObj.searchParams.has('logNo') && !urlObj.pathname.match(/\/[^/]+\/\d+/)) { return; }
                                }
                                if (href.includes('cafe.naver.com')) {
                                    if (!urlObj.searchParams.has('articleid') && !urlObj.pathname.match(/\/[a-zA-Z0-9_-]+\/\d+/)) { return; }
                                }
                            } catch(e) {}
                            
                            if (title.length > 2 && !seenUrls.has(href)) {
                                seenUrls.add(href);
                                
                                let type = "웹문서";
                                if (href.includes("blog.naver.com")) type = "블로그";
                                else if (href.includes("cafe.naver.com")) type = "카페";
                                else if (href.includes("in.naver.com") || href.includes("influencer")) type = "인플루언서";
                                else if (href.includes("youtube.com") || href.includes("tv.naver.com") || href.includes("clip.naver.com") || href.includes("m.wev.naver.com")) type = "동영상/쇼츠";
                                else if (href.includes("post.naver.com")) type = "포스트";
                                else if (href.includes("place.naver.com") || href.includes("map.naver.com") || href.includes("store.naver.com")) type = "플레이스";

                                let cleanTitle = title.substring(0, 80);
                                links.push({ title: cleanTitle, url: href, type: type });
                            }
                        });
                        
                        if (links.length > 0) {
                            if (links[0].type === "인플루언서" && !blockTitle.includes("인플루언서")) {
                                blockTitle = "인플루언서 | " + blockTitle;
                            } else if (links[0].type === "카페" && !blockTitle.includes("카페")) {
                                blockTitle = "카페 | " + blockTitle;
                            } else if (links[0].type === "플레이스" && !blockTitle.includes("플레이스")) {
                                blockTitle = "플레이스 | " + blockTitle;
                            }
                            
                            const blockHash = links.map(l => l.url).join('|');
                            if (!seenBlockHashes.has(blockHash)) {
                                seenBlockHashes.add(blockHash);
                                results.push({
                                    block_title: blockTitle,
                                    links: links.slice(0, 15)
                                });
                            }
                        }
                    });
                    return { blocks: results, rel_kws: [...new Set(rel_kws)] };
                }""")

                # '인기글' 블록을 href 패턴으로 완전 추출(기존 블록 추출이 일부만 잡는 문제 보완)
                try:
                    popular_links = await page.evaluate(r"""() => {
                        const decode = (href) => {
                            try { if (href.includes('m.search.naver.com') && href.includes('url=')) { return decodeURIComponent(new URL(href).searchParams.get('url')); } } catch(e){}
                            return href;
                        };
                        let sec = null;
                        document.querySelectorAll('section, .api_subject_bx').forEach(s => {
                            const h = s.querySelector('h2,h3,.api_title,[role=heading]');
                            if (h && /인기글/.test(h.innerText)) sec = s;
                        });
                        if (!sec) return [];
                        const byUrl = new Map();  // url → 제목(본문 아님)으로 dedup
                        sec.querySelectorAll('a[href]').forEach(a => {
                            let href = decode(a.href);
                            const isBlog = /blog\.naver\.com\/[^\/?#]+\/\d+/.test(href);
                            // 카페는 '글'만(클럽홈/프로필 제외): /클럽/숫자 또는 art=/articleid=
                            const isCafe = /cafe\.naver\.com\/[^\/?#]+\/\d+/.test(href) || /[?&](art|articleid)=/.test(href);
                            const isInf = href.includes('in.naver.com');
                            if (!isBlog && !isCafe && !isInf) return;
                            // 카드 anchor 는 '제목\n본문스니펫' 형태가 많음 → 첫 줄만 취해 제목 후보로.
                            const firstLine = ((a.innerText || '').split('\n').map(s => s.trim()).filter(Boolean)[0] || '').replace(/\s+/g, ' ').slice(0, 80);
                            // 썸네일 숫자배지(예: '26')·초단문·메타는 제외
                            if (!firstLine || firstLine.length < 4) return;
                            if (/^[\d\s.,~%:+\-]+$/.test(firstLine)) return;
                            const type = isCafe ? '카페' : (isInf ? '인플루언서' : '블로그');
                            const prev = byUrl.get(href);
                            // 제목은 보통 본문 스니펫보다 짧다 → 유효 후보 중 더 짧은 첫 줄을 제목으로 채택.
                            if (!prev || firstLine.length < prev.title.length) byUrl.set(href, { title: firstLine, url: href, type: type });
                        });
                        return [...byUrl.values()];
                    }""")
                except Exception as _e:
                    popular_links = []
            except Exception as e:
                print(e)
                blocks = {'blocks': [], 'rel_kws': []}
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
                
        vol_data = await vol_task
        pc_vol = 0
        mo_vol = 0
        if vol_data and len(vol_data) > 0:
            pc_vol = vol_data[0].get('pc', 0)
            mo_vol = vol_data[0].get('mobile', 0)
            
        html_rel_kws = blocks.get('rel_kws', []) if isinstance(blocks, dict) else []
        blocks_data = blocks.get('blocks', []) if isinstance(blocks, dict) else blocks
            
        related_keywords_data = []
        kw_list = await self.fetch_related_keywords(keyword)
        
        all_kws = list(set(kw_list + html_rel_kws))
        
        if all_kws:
            rel_vols = await self.fetch_keyword_volumes(all_kws)
            vol_map = {}
            for v in rel_vols:
                vkw = v.get('keyword', '').replace(' ', '')
                vol_map[vkw] = {
                    'pc': v.get('pc', 0),
                    'mo': v.get('mobile', 0)
                }
            
            lookup_main = keyword.replace(' ', '')
            related_keywords_data.append({
                "keyword": keyword,
                "pc_vol": vol_map.get(lookup_main, {}).get('pc', pc_vol),
                "mo_vol": vol_map.get(lookup_main, {}).get('mo', mo_vol),
                "type": "자동완성" # 메인
            })
            
            for kw in html_rel_kws:
                lookup_kw = kw.replace(' ', '')
                if kw != keyword:
                    related_keywords_data.append({
                        "keyword": kw,
                        "pc_vol": vol_map.get(lookup_kw, {}).get('pc', 0),
                        "mo_vol": vol_map.get(lookup_kw, {}).get('mo', 0),
                        "type": "함께찾는"
                    })
                    
            for kw in kw_list:
                if kw not in html_rel_kws and kw != keyword:
                    lookup_kw = kw.replace(' ', '')
                    related_keywords_data.append({
                        "keyword": kw,
                        "pc_vol": vol_map.get(lookup_kw, {}).get('pc', 0),
                        "mo_vol": vol_map.get(lookup_kw, {}).get('mo', 0),
                        "type": "자동완성"
                    })
                
        filtered_blocks = []
        for b in blocks_data:
            btitle = b['block_title'].replace("\n", ' ').strip()
            if "안내" in btitle and "플레이스" in btitle:
                btitle = "플레이스"
            elif "새로 오픈" in btitle:
                btitle = "새로 오픈"
            
            if "연관" not in btitle and "많이 찾는" not in btitle:
                b['block_title'] = btitle
                
                clean_links = [l for l in b['links'] if "오류" not in l['title'] and l['title'] != "웹문서" and "전체필터" not in l['title'] and "OpenStreetMap" not in l['title'] and "ader.naver.com" not in l['url'] and "내 업체 등록하기" not in l['title'] and "클립 고객센터" not in l['title'] and "Keep에 저장" not in l['title'] and "Keep에 바로가기" not in l['title']]
                if clean_links:
                    b['links'] = clean_links
                    filtered_blocks.append(b)
                    
        # 블로그 탭(순위 그대로) 별도 수집 + 인기글 완전 추출을 앞에 배치
        # → 사용자가 '블로그'와 '인기글'을 각각 체크 선택할 수 있게 두 블록을 상단 고정.
        blog_tab_links = await self._fetch_blog_tab(keyword, limit=20)
        final_blocks = []
        if blog_tab_links:
            final_blocks.append({"block_title": "블로그", "links": blog_tab_links})
        if popular_links:
            # 깨끗한 제목 우선 정렬 후 상위 30
            final_blocks.append({"block_title": "인기글", "links": popular_links[:30]})
        # 나머지(플레이스/클립/새로오픈 등)는 참고용으로 뒤에 — 단, 블로그/인기글 중복 제외
        for b in filtered_blocks:
            bt = b.get("block_title", "")
            if bt == "블로그" or "인기글" in bt:
                continue
            final_blocks.append(b)

        return {
            "keyword": keyword,
            "pc_vol": pc_vol,
            "mo_vol": mo_vol,
            "related_keywords": related_keywords_data,
            "blocks": final_blocks
        }

    async def generate_winning_formula(self, keyword: str, metrics: list, top_keywords: list) -> str:
        """AI를 통해 상위 노출 공식(Winning Formula) 요약 리포트 생성"""
        print("[SEO] 상위노출 가이드라인 생성 중...")
        
        # 분석은 상위 5개 데이터만 사용 (비용 및 노이즈 방지)
        top_5_metrics = metrics[:5]
        
        avg_char = sum(m.get('char_count', 0) for m in top_5_metrics) // len(top_5_metrics) if top_5_metrics else 0
        avg_img = sum(m.get('img_count', 0) for m in top_5_metrics) // len(top_5_metrics) if top_5_metrics else 0
        
        inf_count = sum(1 for m in top_5_metrics if m.get('type') == '인플루언서')
        # 실제 type 값은 '인기카페'/'인기블로그' → 존재하지 않는 '인기글' 대신 '인기' 포함으로 집계
        pop_count = sum(1 for m in top_5_metrics if '인기' in (m.get('type') or ''))
        
        # 난이도 계산 로직
        difficulty_score = (inf_count * 15) + (pop_count * 10)
        if avg_char >= 2000: difficulty_score += 15
        elif avg_char >= 1000: difficulty_score += 10
        difficulty_score = min(difficulty_score, 100)
        
        keyword_str = ", ".join([f"{k['keyword']}({k['count']}회)" for k in top_keywords[:10]])
        
        # 선택된 포스팅 정보 구성
        blog_list_str = "\n".join([f"- {m.get('title','')} (분류: {m.get('type','')}, 글자수: {m.get('char_count',0)}자, 이미지: {m.get('img_count',0)}장)" for m in metrics])
        
        prompt = f"""
        당신은 SEO 마케팅 전문가입니다. 검색어 "{keyword}"에 대해 사용자가 직접 선택한 {len(metrics)}개의 블로그를 분석한 결과입니다.
        
        [분석 데이터 요약]
        - 키워드 난이도 점수: {difficulty_score} / 100점
        - 인플루언서 글 비율: {inf_count}/{len(metrics)}
        - 인기글 비율: {pop_count}/{len(metrics)}
        - 평균 글자수: {avg_char}자 (공백 제외)
        - 평균 이미지 수: {avg_img}장
        - 핵심 서브 키워드 및 노출 빈도: {keyword_str}
        
        [선택된 블로그 글감(포스팅)별 세부 분류 현황]
{blog_list_str}
        
        위 데이터를 바탕으로 일반 블로거가 이 키워드에서 상위에 노출되기 위한 "Winning Formula(우회 마케팅 전략)"을 마크다운 형식으로 작성해주세요.
        반드시 다음 사항을 포함해야 합니다:
        1. **전체 요약**: 가장 먼저, 위 데이터를 바탕으로 현재 키워드의 경쟁 상태와 사용자가 선택한 블로그들의 전반적인 특징을 2~3줄로 깔끔하게 요약해주세요.
        2. **선택된 글감별 특징 요약**: [선택된 블로그 글감별 세부 분류 현황]을 참고하여, 어떤 종류의 포스팅(인플루언서, 인기글, 일반 등)이 많은지 분석해주세요.
        3. **경쟁 강도 및 난이도 진단**: {difficulty_score}점을 바탕으로 현재 상황 진단. (인플루언서가 많으면 정면승부가 어렵다고 경고)
        4. **차별화된 스펙 목표치**: 평균 글자수({avg_char})와 평균 이미지수({avg_img})에 각각 20%를 더한 구체적인 숫자(목표 글자수, 목표 사진 수) 제시.
        5. **키워드 활용법**: 핵심 서브 키워드 중 상위 3개를 본문에 어떻게 자연스럽게 녹일지 예시 문장 포함.
        """
        
        try:
            import asyncio
            response_text = await asyncio.wait_for(self.soul.generate_content(prompt), timeout=15.0)
            return response_text
        except Exception as e:
            return f"가이드라인 생성 실패: {e}"

    @staticmethod
    def count_phrase_occurrences(text: str, phrase: str) -> int:
        if not phrase:
            return 0
        normalized_text = re.sub(r'\s+', ' ', text).strip()
        exact_matches = normalized_text.count(phrase)
        if ' ' in phrase:
            no_space_text = re.sub(r'\s+', '', normalized_text)
            no_space_phrase = phrase.replace(' ', '')
            compact_matches = no_space_text.count(no_space_phrase)
            return max(exact_matches, compact_matches)
        return exact_matches

    async def generate_custom_seo_report(self, texts: list) -> str:
        """사용자가 지정한 D.I.A+ 역엔지니어링 프롬프트를 사용하여 분석 리포트 생성"""
        if not texts:
            return "분석할 텍스트가 없습니다."
        
        combined_text = "\n\n---\n\n".join([f"[{i+1}위 포스팅 본문]\n{t[:3000]}" for i, t in enumerate(texts)])
        
        prompt = f"""너는 네이버 검색 엔진 최적화(SEO) 및 D.I.A+ 로직 분석 전문가야. 내가 제공하는 텍스트는 현재 특정 키워드로 네이버 1~3위에 상위노출된 경쟁 블로그 글들이야. 이 글들을 분석해서 아래의 수치화된 기준에 따라 리포트를 작성해 줘.

[분석 및 추출 기준]
메인 키워드 및 밀도 파악: 가장 많이 반복된 핵심 키워드 1개를 찾고, 평균 몇 회 반복되었는지 계산해 줘.
연관 속성 키워드(LSI) 10개 추출: 메인 키워드 외에 문맥상 함께 쓰인 구체적인 관련 단어, 명사, 전문 용어 10개를 빈도수 순으로 추출해 줘.
문서 구조 분석: 소제목(H태그)은 평균 몇 개 사용되었으며, 표나 리스트 형태가 포함되어 있는지 파악해 줘.
경험적(D.I.A+) 요소 추출: "내돈내산", "직접 해보니", "단점은" 등 작성자의 1차 경험을 나타내는 주관적인 표현 패턴을 3개 이상 찾아 줘.

[분석할 텍스트 입력]:
{combined_text}
"""
        try:
            if not self.soul.gemini_client:
                return "⚠️ 환경설정 메뉴에서 Gemini API 키를 입력하셔야 AI 분석이 가능합니다."
            return await self.soul._call_gemini(prompt)
        except Exception as e:
            return f"가이드라인 생성 실패: {e}"

    # ═══════════════════════════════════════
    # 🛡️ 블로그 진단 및 순위 추적 (Phase 6)
    # ═══════════════════════════════════════

    def clean_text(self, text: str) -> str:
        """대형 언어 모델 처리를 위한 텍스트 정제 및 PII(개인정보) 마스킹"""
        # 1. 네이버 UI 껍데기 노이즈(메뉴, 알림 등) 방어적 필터링
        noise_words = [
            r'댓글알림음', r'폰트 설정', r'본문 기타 기능', r'내소식', r'이웃추가', 
            r'스크랩하기', r'URL 복사', r'신고하기', r'게시판', r'카페가입', r'전체글보기'
        ]
        for word in noise_words:
            text = re.sub(word, '', text)

        # 2. PII(개인정보) 마스킹 (이메일, 전화번호 등 필터링)
        text = re.sub(r'[\w\.-]+@[\w\.-]+', '<EMAIL>', text)
        text = re.sub(r'\d{2,3}-\d{3,4}-\d{4}', '<PHONE>', text)
        
        # 3. 불필요한 공백 제거
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def extract_rule_based_properties(self, text: str) -> dict:
        """네이버 D.I.A+ 시스템 모사: 경험적 속성 및 스니펫 후보 추출"""
        properties = {}
        
        # 가격 정보 추출 패턴
        price_pattern = re.compile(r'(\d{1,3}(,\d{3})*원|\$\d+(,\d{3})*|[일이삼사오육칠팔구십백천만]+원)')
        properties['prices'] = [match.group() for match in price_pattern.finditer(text)]
        
        # 순서 및 논리적 전개 패턴
        sequence_pattern = re.compile(r'(첫\s*번째|두\s*번째|\d\.\s)')
        properties['sequences'] = [match.group() for match in sequence_pattern.finditer(text)]
        
        # 주관적 평가/의견 패턴
        opinion_pattern = re.compile(r'(별로였|좋더|추천|아쉬|단점|장점|내돈내산|직접)')
        properties['opinions'] = [match.group() for match in opinion_pattern.finditer(text)]
        
        return properties

    async def fetch_blog_stats_by_id(self, blog_id: str) -> dict:
        """네이버 블로그 공개 프로필 통계 수집 — 로그인 불필요, m.blog.naver.com __NEXT_DATA__ 활용"""
        import aiohttp
        headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15"}
        url = f"https://m.blog.naver.com/{blog_id}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    html = await resp.text()
                    match = re.search(r'window\.__NEXT_DATA__\s*=\s*(\{.*\});\s*(?:window\.|</script>)', html, re.DOTALL)
                    if match:
                        data = json.loads(match.group(1))
                        user_info = data['props']['pageProps']['initialState']['user']['userInfo']
                        return {
                            "blog_id": blog_id,
                            "blog_name": user_info.get('blogName', ''),
                            "subscriber_count": user_info.get('subscriberCount', 0),
                            "visitor_count": user_info.get('visitorCount', 0),
                            "today_visitor_count": user_info.get('todayVisitorCount', 0),
                            "total_post_count": user_info.get('totalPostCount', 0),
                            "created_date": user_info.get('blogCreatedDate', ''),
                        }
        except Exception as e:
            print(f"[SEO] 블로그 통계 수집 실패 ({blog_id}): {e}")
        return {}

    # 네이버 카페 등급 사다리(6단계) — 카페 홈 `.ico_rank rankNN` + `<em>등급명</em>`
    _CAFE_GRADE_TIERS = {'씨앗': 1, '새싹': 2, '잎새': 3, '가지': 4, '나무': 5, '숲': 6}

    @staticmethod
    async def fetch_cafe_grade_info(session, cafe_slug: str) -> dict:
        """카페 홈 HTML에서 카페 등급(씨앗~숲)과 대표카페 여부를 추출.

        반환: {cafe_grade_name, cafe_grade_tier(1~6), is_official_cafe}
        실패 시 빈 dict. (로그인·비공개 무관 — 카페 홈은 공개)
        """
        import re
        if not cafe_slug or cafe_slug in ('ArticleRead.nhn',):
            return {}
        try:
            async with session.get(f"https://cafe.naver.com/{cafe_slug}") as resp:
                if resp.status != 200:
                    return {}
                html = await resp.text(errors='ignore')

            out = {}
            # 카페 등급: <span class="ico_rank rank30"></span><em>숲</em>
            gm = re.search(r'ico_rank\s+rank(\d+)"[^>]*></span>\s*<em>([^<]+)</em>', html)
            if gm:
                name = gm.group(2).strip()
                out['cafe_grade_name'] = name
                # 등급명 우선, 없으면 rank 숫자(5단위)로 tier 추정
                out['cafe_grade_tier'] = SeoAnalyzer._CAFE_GRADE_TIERS.get(
                    name, max(1, min(6, int(gm.group(1)) // 5)))
            # 대표카페: NAVER 대표카페 마크
            out['is_official_cafe'] = ('대표카페' in html) or ('popular_40x32' in html)
            return out
        except Exception as e:
            print(f"[SEO] 카페 등급 수집 실패 ({cafe_slug}): {e}")
            return {}

    @staticmethod
    def _calculate_authority_scores(cafe_author_info: dict) -> dict:
        """카페 작성자 / 카페 권위 지수 v2 (공개 데이터 기반).

        Author Authority (0~100):
            멤버 등급(0~40) + 인기멤버 보너스(0/15) + 글 호응도(0~45)
            └ 호응도 = 조회(0~15) + 좋아요(0~12) + 댓글(0~11) + 스크랩(0~7) (log scale)

        Cafe Authority (0~100):
            회원수(0~55) + 카페 등급 씨앗~숲(0~30) + 대표카페(0/15)

        v2 수집 데이터:
            - 카페 등급(cafe_grade_tier 1~6: 씨앗/새싹/잎새/가지/나무/숲) — 카페 홈 HTML
            - 대표카페 여부(is_official_cafe) — 카페 홈 '대표카페' 마크
            - 스크랩수(scrap_count) — 카페 article API
        ⚠ 미수집(비공개/로그인 필요): 작성자 가입일·작성글수, 카페 일일활성도.
        """
        import math
        info = cafe_author_info or {}

        # ─ Author Authority ────────────────────────────────────────
        tier = info.get('level_tier')
        # tier 1=2.7, tier 5=13.3, tier 13=34.7, tier 15+=40 (linear, cap)
        tier_score = min(40.0, max(0.0, (tier or 0) / 15.0 * 40.0))

        popular_bonus = 15.0 if info.get('is_popular') else 0.0

        view  = max(0, int(info.get('view_count') or 0))
        like  = max(0, int(info.get('like_count') or 0))
        comm  = max(0, int(info.get('comment_count') or 0))
        scrap = max(0, int(info.get('scrap_count') or 0))
        # 조회수 1000 / 좋아요·댓글 50 / 스크랩 30 을 만점 기준 (log scale)
        view_pts  = min(15.0, math.log1p(view)  / math.log(1001) * 15.0)
        like_pts  = min(12.0, math.log1p(like)  / math.log(51)   * 12.0)
        comm_pts  = min(11.0, math.log1p(comm)  / math.log(51)   * 11.0)
        scrap_pts = min(7.0,  math.log1p(scrap) / math.log(31)   * 7.0)
        engagement = view_pts + like_pts + comm_pts + scrap_pts

        author_score = round(min(100.0, tier_score + popular_bonus + engagement), 1)

        # ─ Cafe Authority ─────────────────────────────────────────
        member = max(0, int(info.get('cafe_member') or 0))
        # 회원수 정규화(0~55): 1만=29pt, 10만=42pt, 100만=52pt, 200만+=55pt
        if member <= 0:
            member_pts = 0.0
        else:
            member_pts = min(55.0, math.log10(member) / math.log10(2_000_000) * 55.0)

        # 카페 등급(0~30): 씨앗1 / 새싹2 / 잎새3 / 가지4 / 나무5 / 숲6
        grade_tier = info.get('cafe_grade_tier')
        cafe_grade_pts = min(30.0, max(0.0, (grade_tier or 0) / 6.0 * 30.0))

        # 대표카페(0/15): NAVER 대표카페 마크
        official_pts = 15.0 if info.get('is_official_cafe') else 0.0

        cafe_score = round(min(100.0, member_pts + cafe_grade_pts + official_pts), 1)

        def grade(s: float) -> str:
            if s >= 80: return 'S'
            if s >= 65: return 'A'
            if s >= 45: return 'B'
            if s >= 25: return 'C'
            return 'D'

        return {
            'author_score': author_score,
            'author_grade': grade(author_score),
            'cafe_score':   cafe_score,
            'cafe_grade':   grade(cafe_score),
            'score_breakdown': {
                'tier_pts':      round(tier_score, 1),
                'popular_bonus': popular_bonus,
                'engagement':    round(engagement, 1),
                'view_pts':      round(view_pts, 1),
                'like_pts':      round(like_pts, 1),
                'comment_pts':   round(comm_pts, 1),
                'scrap_pts':     round(scrap_pts, 1),
                'cafe_member_pts':  round(member_pts, 1),
                'cafe_grade_pts':   round(cafe_grade_pts, 1),
                'cafe_official_pts': official_pts,
            },
        }

    async def fetch_cafe_author_info(self, target_page) -> dict:
        """카페 iframe(cafe_main) 내부에서 작성자/카페 권위 데이터 추출.

        호출 시점: analyze_multiple_urls 의 카페 분기에서 frame 로딩 직후.
        반환 키:
            nickname, level_name, level_tier, is_popular, member_hash,
            view_count, like_count, comment_count, post_date,
            cafe_name, cafe_desc, cafe_member, (선택)club_id
        """
        try:
            # 좋아요/댓글 카운트는 lazy 로딩 모듈(_cafeReactionModule)이라
            # 해당 요소를 viewport 에 노출시켜 IntersectionObserver 발화시킨다.
            try:
                await target_page.evaluate(
                    """
                    () => {
                      const el = document.querySelector('.ReactionLikeIt')
                              || document.querySelector('.button_comment');
                      if (el && el.scrollIntoView) el.scrollIntoView({ block: 'center' });
                    }
                    """
                )
                await target_page.wait_for_timeout(900)
            except Exception:
                pass

            info = await target_page.evaluate(
                """
                () => {
                  const T = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? (el.innerText || el.textContent || '').trim() : '';
                  };
                  const N = (s) => {
                    if (!s) return 0;
                    const m = s.match(/[\\d,]+/);
                    return m ? parseInt(m[0].replace(/,/g, ''), 10) : 0;
                  };

                  // 등급 sprite: #1_1-usage / #13_120-usage → 첫 숫자 = 카페 내 등급 티어
                  const sprite = (document.querySelector('i.LevelIcon')?.getAttribute('style') || '');
                  const lm = sprite.match(/#(\\d+)_(\\d+)-usage/);

                  // 멤버 hash: /ca-fe/cafes/{clubid}/members/{hash}
                  const memberHref = document.querySelector('.ArticleWriterProfile a[href]')?.getAttribute('href') || '';
                  const hashMatch = memberHref.match(/\\/members\\/([A-Za-z0-9_-]+)/);

                  // 등급명: em.nick_level 의 텍스트 (내부 i 태그 제거 후)
                  let levelName = '';
                  const lvEl = document.querySelector('em.nick_level');
                  if (lvEl) {
                    const clone = lvEl.cloneNode(true);
                    clone.querySelectorAll('i').forEach(i => i.remove());
                    levelName = (clone.innerText || clone.textContent || '').trim();
                  }

                  return {
                    nickname:      T('.nick_box .nickname'),
                    level_name:    levelName,
                    level_tier:    lm ? parseInt(lm[1], 10) : null,
                    is_popular:    !!document.querySelector('em.popular_mark'),
                    member_hash:   hashMatch ? hashMatch[1] : null,
                    view_count:    N(T('.article_info .count')),
                    like_count:    N(T('.like_no em.u_cnt._count')),
                    comment_count: N(T('.button_comment')),
                    post_date:     T('.article_info .date'),
                    cafe_name:     T('.cafe_info .cafe_name'),
                    cafe_desc:     T('.cafe_info .cafe_desc'),
                    cafe_member:   N(T('.cafe_info .cafe_member em')),
                  };
                }
                """
            )
            return info or {}
        except Exception as e:
            print(f"[SEO] 카페 작성자 정보 추출 실패: {e}")
            return {}

    async def analyze_multiple_urls(self, urls: list) -> dict:
        """네이버 블로그/카페 URL을 병렬(동시) 수집 및 분석 (API 기반 고속 통신)"""
        import aiohttp
        from bs4 import BeautifulSoup
        import asyncio
        import re
        import json
        import base64
        
        results = {}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://search.naver.com/"
        }

        async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as session:
            semaphore = asyncio.Semaphore(5)
            
            async def process_url(raw_url):
                async with semaphore:
                    try:
                        url = raw_url
                        
                        # 리다이렉트 추적 (in.naver.com 등 단축/리다이렉트 URL 대비)
                        if "in.naver.com" in url or "naver.me" in url:
                            try:
                                async with session.get(url, allow_redirects=True) as r:
                                    url = str(r.url)
                            except Exception:
                                pass

                        is_cafe = "cafe.naver.com" in url
                        is_blog = "blog.naver.com" in url
                        blog_id = "미상"
                        cafe_author_info = {}
                        
                        raw_text = ""
                        html_source = ""
                        title_str = "제목 없음"
                        
                        if is_blog:
                            match = re.search(r'blog\.naver\.com/([^/]+)/(\d+)', url)
                            if not match:
                                query_match = re.search(r'blogId=([^&]+).*logNo=(\d+)', url)
                                if query_match:
                                    blog_id, log_no = query_match.group(1), query_match.group(2)
                                else:
                                    return raw_url, {"error": "블로그 메인(홈) 주소입니다. 개별 포스팅 주소가 필요합니다."}
                            else:
                                blog_id, log_no = match.group(1), match.group(2)
                                
                            post_view_url = f"https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={log_no}"
                            async with session.get(post_view_url) as resp:
                                if resp.status != 200:
                                    return raw_url, {"error": f"블로그 본문을 가져올 수 없습니다. (상태코드: {resp.status})"}
                                html = await resp.text()
                                if "해당 블로그가 비공개 상태이거나" in html or "존재하지 않는" in html:
                                    return raw_url, {"error": "비공개이거나 삭제된 게시글입니다."}
                                
                                html_source = html
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # 블로그 제목 추출
                                title_el = soup.select_one('.se-title-text, .pcol1, .se_title, head > title')
                                if title_el:
                                    title_str = title_el.get_text(strip=True).replace(' : 네이버 블로그', '')
                                
                                content_div = soup.select_one('.se-main-container, #postViewArea')
                                if not content_div:
                                    return raw_url, {"error": "본문 영역(.se-main-container)을 찾을 수 없습니다."}
                                raw_text = content_div.get_text(separator='\n', strip=True)
                                
                        elif is_cafe:
                            club_id = None
                            article_id = None
                            
                            art_match = re.search(r'art=[^.]+\.[^.]+\.([^.]+)', url)
                            if art_match:
                                payload = art_match.group(1)
                                payload += '=' * (-len(payload) % 4)
                                try:
                                    data = json.loads(base64.urlsafe_b64decode(payload).decode('utf-8'))
                                    article_id = data.get('articleId')
                                except Exception:
                                    try:
                                        data = json.loads(base64.b64decode(payload).decode('utf-8'))
                                        article_id = data.get('articleId')
                                    except Exception:
                                        pass
                                    
                            if not article_id:
                                cafe_match = re.search(r'/cafes/(\d+)/articles/(\d+)', url)
                                if cafe_match:
                                    club_id, article_id = cafe_match.group(1), cafe_match.group(2)
                                else:
                                    aid_match = re.search(r'articleid=(\d+)', url.lower()) or re.search(r'/(\d+)(?:\?|$)', url)
                                    cid_match = re.search(r'clubid=(\d+)', url.lower())
                                    if aid_match: article_id = aid_match.group(1)
                                    if cid_match: club_id = cid_match.group(1)
                            
                            if not club_id and article_id:
                                cafe_name_match = re.search(r'cafe\.naver\.com/([^/]+)', url)
                                if cafe_name_match:
                                    cafe_name = cafe_name_match.group(1).split('?')[0]
                                    if cafe_name != 'ArticleRead.nhn':
                                        try:
                                            async with session.get(f"https://cafe.naver.com/{cafe_name}") as resp:
                                                cafe_home_html = await resp.text()
                                                cid_match = re.search(r'clubid=(\d+)', cafe_home_html.lower()) or re.search(r'g_sclubid\s*=\s*[\"\']?(\d+)', cafe_home_html.lower())
                                                if cid_match:
                                                    club_id = cid_match.group(1)
                                        except Exception:
                                            pass
                                        
                            if not club_id or not article_id:
                                return raw_url, {"error": "카페 게시글의 clubid 또는 articleid를 추출할 수 없습니다."}
                                
                            api_url = f"https://apis.naver.com/cafe-web/cafe-articleapi/v2.1/cafes/{club_id}/articles/{article_id}"
                            async with session.get(api_url) as resp:
                                if resp.status != 200:
                                    return raw_url, {"error": f"카페 본문을 가져올 수 없습니다. (상태코드: {resp.status})"}
                                api_data = await resp.json()
                                if 'article' not in api_data.get('result', {}):
                                    return raw_url, {"error": api_data.get('result', {}).get('reason', '비공개이거나 삭제된 게시글입니다.')}
                                
                                article_data = api_data['result']['article']
                                title_str = article_data.get('subject', '제목 없음')
                                html_source = article_data.get('contentHtml', '')
                                
                                soup = BeautifulSoup(html_source, 'html.parser')
                                raw_text = soup.get_text(separator='\n', strip=True)
                                
                                member_key = article_data.get('writer', {}).get('memberKey')
                                if member_key:
                                    blog_id = member_key

                                # 작성자/카페 권위 데이터 추출 — API JSON에 모두 포함(Playwright 불필요).
                                _res = api_data.get('result', {})
                                _writer = article_data.get('writer', {})
                                _cafe = _res.get('cafe', {})
                                _icon = _writer.get('memberLevelIconUrl', '') or ''
                                # 아이콘 URL 예: /levelicon/1/13_120.gif
                                #   → 경로의 1 = 테마 세트 id, 파일명 13_120 의 13 = 실제 카페 등급.
                                #     파일명 첫 숫자(레벨)를 우선 추출, 실패 시 memberLevel 숫자 폴백.
                                _tier_m = re.search(r'/levelicon/\d+/(\d+)_\d+', _icon)
                                _post_date = ''
                                _wd = article_data.get('writeDate')
                                if _wd:
                                    try:
                                        from datetime import datetime
                                        _post_date = datetime.fromtimestamp(int(_wd) / 1000).strftime('%Y.%m.%d %H:%M')
                                    except Exception:
                                        _post_date = ''
                                cafe_author_info = {
                                    'nickname':      _writer.get('nick', ''),
                                    'level_name':    _writer.get('memberLevelName', ''),
                                    'level_tier':    int(_tier_m.group(1)) if _tier_m else None,
                                    'is_popular':    bool(_writer.get('currentPopularMember')),
                                    'member_hash':   member_key,
                                    'view_count':    int(article_data.get('readCount', 0) or 0),
                                    'like_count':    0,  # 카페 좋아요수는 별도 reaction API 필요(현재 미수집)
                                    'comment_count': int(article_data.get('commentCount', 0) or 0),
                                    'scrap_count':   int(article_data.get('scrapCount', 0) or 0),
                                    'post_date':     _post_date,
                                    'cafe_name':     _cafe.get('name', ''),
                                    'cafe_desc':     _cafe.get('introduction', ''),
                                    'cafe_member':   int(_cafe.get('memberCount', 0) or 0),
                                    'club_id':       club_id,
                                }

                                # 좋아요수 — 네이버 통합 LikeIt(공감) API. article API엔 없어서 별도 호출.
                                #   route-like.naver.com/v1/search/contents?q=CAFE[{club}_{cafeUrl}_{article}]&pool=cafe
                                try:
                                    _curl = _cafe.get('url', '')
                                    if _curl and club_id and article_id:
                                        import urllib.parse as _up
                                        _q = _up.quote(f'CAFE[{club_id}_{_curl}_{article_id}]')
                                        _like_url = (f'https://route-like.naver.com/v1/search/contents'
                                                     f'?suppress_response_codes=true&q={_q}&pool=cafe')
                                        async with session.get(_like_url) as _lr:
                                            if _lr.status == 200:
                                                _lt = await _lr.text()
                                                _lm = re.search(r'^[^({]*\((.*)\)\s*;?\s*$', _lt.strip(), re.S)
                                                _ld = json.loads(_lm.group(1) if _lm else _lt)
                                                for _c in _ld.get('contents', []):
                                                    for _rx in _c.get('reactions', []):
                                                        if _rx.get('reactionType') == 'like':
                                                            cafe_author_info['like_count'] = int(_rx.get('count', 0) or 0)
                                except Exception as _le:
                                    print(f"[SEO] 카페 좋아요수 수집 실패: {_le}")

                                # 카페 등급(씨앗~숲) + 대표카페 여부 — 카페 홈 HTML 공개
                                try:
                                    _grade = await self.fetch_cafe_grade_info(session, _cafe.get('url', ''))
                                    if _grade:
                                        cafe_author_info.update(_grade)
                                except Exception as _ge:
                                    print(f"[SEO] 카페 등급 수집 실패: {_ge}")

                        else:
                            return raw_url, {"error": "지원되지 않는 URL 형식입니다. (네이버 블로그/카페만 지원)"}
                            
                        if not raw_text:
                            return raw_url, {"error": "본문 내용이 비어있습니다."}
                            
                        cleaned_text = self.clean_text(raw_text)
                        rule_props = self.extract_rule_based_properties(cleaned_text)
                        
                        soup = BeautifulSoup(html_source, 'html.parser')
                        
                        actual_images = []
                        for img in soup.find_all('img'):
                            classes = img.get('class', [])
                            if any('se-image-resource' in c or 'se-viewer-image' in c or 'se-component-image' in c for c in classes):
                                actual_images.append(img)
                        if not actual_images and len(soup.find_all('img')) > 0:
                            for img in soup.find_all('img'):
                                src = img.get('src', '').lower()
                                if 'sticker' not in src and 'emoji' not in src and 'profile' not in src and 'nametag' not in src:
                                    actual_images.append(img)
                                    
                        img_count = len(actual_images)
                        link_count = len(soup.find_all('a'))
                        table_count = len(soup.find_all('table'))
                        h_tag_count = len(soup.find_all(['h2', 'h3', 'h4']))
                        
                        total_char = len(cleaned_text)
                        char_count = len(cleaned_text.replace(" ", ""))
                        space_count = cleaned_text.count(" ")
                        sentence_count = len(re.findall(r'[.!?]+', cleaned_text)) or 1
                        ko_char = len(re.findall(r'[가-힣]', cleaned_text))
                        en_char = len(re.findall(r'[A-Za-z]', cleaned_text))
                        num_char = len(re.findall(r'\d', cleaned_text))
                        
                        if len(cleaned_text) < 50:
                            return raw_url, {"error": "본문이 너무 짧습니다."}
                            
                        # 카페 작성자/카페 권위 점수 병합 (닉네임이 추출된 경우만)
                        if is_cafe and cafe_author_info.get('nickname'):
                            cafe_author_info.update(self._calculate_authority_scores(cafe_author_info))

                        blog_info = {}
                        if blog_id and blog_id != "미상" and not is_cafe:
                            blog_info = await self.fetch_blog_stats_by_id(blog_id)
                            
                        return raw_url, {
                            "blog_id": blog_id,
                            "blog_info": blog_info,
                            "cafe_author_info": cafe_author_info,
                            "title": title_str,
                            "char_count": char_count,
                            "total_char": total_char,
                            "space_count": space_count,
                            "img_count": img_count,
                            "link_count": link_count,
                            "table_count": table_count,
                            "h_tag_count": h_tag_count,
                            "sentence_count": sentence_count,
                            "ko_char": ko_char,
                            "en_char": en_char,
                            "num_char": num_char,
                            "rule_properties": rule_props,
                            "text_sample": cleaned_text[:200] + "...",
                            "full_text": cleaned_text,
                            "top_keywords": [],
                            "main_keyword": "",
                            "sub_keywords": [],
                            "text_type": "네이버 카페" if is_cafe else "네이버 블로그",
                            "type_color": "#7c3aed" if is_cafe else "#16a34a",
                            "source": "네이버 카페" if is_cafe else "네이버 블로그",
                        }
                    except Exception as e:
                        return raw_url, {"error": f"분석 중 오류: {str(e)}"}

            tasks = [process_url(u) for u in urls]
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in completed:
                if isinstance(res, Exception):
                    continue
                raw_url, result = res
                results[raw_url] = result
                
        return results



    async def track_my_ranking(self, blog_id: str, keyword: str, max_pages: int = 5) -> dict:
        """네이버 검색 결과에서 내 블로그의 순위를 추적"""
        print(f"[SEO] '{keyword}'에 대한 '{blog_id}' 순위 추적 시작...")
        search_url = f"https://search.naver.com/search.naver?where=view&query={keyword}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = await browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            
            try:
                await page.goto(search_url, timeout=15000)
                
                # 스크롤을 내려가며 링크 수집
                found_rank = -1
                for i in range(max_pages):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1000)
                    
                    elements = await page.query_selector_all('a.title_link, a.api_txt_lines.total_tit')
                    valid_links = []
                    for idx, el in enumerate(elements):
                        href = await el.get_attribute('href')
                        if href and blog_id in href:
                            found_rank = (i * len(elements)) + idx + 1
                            break
                    if found_rank > 0: break
                
                return {"rank": found_rank, "keyword": keyword, "blog_id": blog_id}
            except Exception as e:
                print(f"[SEO] 순위 추적 중 오류: {e}")
                return {"rank": -1, "keyword": keyword, "error": str(e)}
            finally:
                await browser.close()

    async def analyze_serp_structure(self, keyword: str) -> dict:
        """네이버 검색 결과(SERP)의 구조 분석 (광고, 클립, 블로그, 인플루언서 등 순서 및 내용)"""
        url = f"https://m.search.naver.com/search.naver?where=m&query={keyword}"
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B)")
            page = await context.new_page()
            
            try:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                
                # 1. 월간 검색량 (간이 추출 - 실제로는 API 필요하지만 여기선 스크래핑 시도)
                # 검색량 노출 영역이 있는 경우만 가능
                
                # 2. 섹션별 구조 분석
                sections = []
                # 모든 섹션 컨테이너 추출
                containers = await page.locator("section.api_subject_bx, div.api_subject_bx").all()
                
                for container in containers:
                    title_el = container.locator("h2.api_title, .api_title_main")
                    if await title_el.count() > 0:
                        s_title = await title_el.inner_text()
                        # 섹션 타입 판별
                        s_type = "일반"
                        if "광고" in s_title: s_type = "AD"
                        elif "클립" in s_title: s_type = "CLIP"
                        elif "브랜드" in s_title: s_type = "BRAND"
                        elif "인플루언서" in s_title: s_type = "INFLUENCER"
                        elif "VIEW" in s_title or "블로그" in s_title: s_type = "BLOG"
                        elif "웹사이트" in s_title: s_type = "WEB"
                        
                        # 하위 아이템 추출
                        items = []
                        links = await container.locator("a.api_txt_lines, a.name").all()
                        for link in links[:3]:
                            txt = await link.inner_text()
                            href = await link.get_attribute("href")
                            if txt.strip():
                                items.append({"text": txt.strip(), "link": href})
                        
                        sections.append({"title": s_title.strip(), "type": s_type, "items": items})
                
                # 3. 연관 검색어
                related = []
                rel_links = await page.locator(".lst_related_srch a").all()
                for rel in rel_links:
                    related.append(await rel.inner_text())

                return {
                    "keyword": keyword,
                    "sections": sections,
                    "related": related
                }
            except Exception as e:
                print(f"Error in check_blog_index: {e}")
                return {"error": str(e)}
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass



    async def fetch_latest_posts(self, blog_id: str, limit: int = 5) -> list:
        """블로그 아이디로 최신 포스팅 목록(URL, 제목) 가져오기"""
        url = f"https://blog.naver.com/PostList.naver?blogId={blog_id}&categoryNo=0&from=postList"
        posts = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded")
                # 최신글 아이템 추출 (모바일 버전이 더 쉬울 수 있음)
                m_url = f"https://m.blog.naver.com/{blog_id}"
                await page.goto(m_url)
                await page.wait_for_timeout(2000)
                
                items = await page.locator("li.item").all()
                for item in items[:limit]:
                    title_el = item.locator(".title")
                    link_el = item.locator("a")
                    if await title_el.count() > 0:
                        title = await title_el.inner_text()
                        href = await link_el.first.get_attribute("href")
                        # https://m.blog.naver.com/id/12345 형태
                        posts.append({"title": title.strip(), "url": href})
            except Exception as e:
                print(f"Error in search_blogs: {e}")
                return []
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass
        return posts

    async def verify_post_status(self, url: str, title: str) -> dict:
        """블로그 글의 누락 및 저품질 검증 (고도화)"""
        import re
        # 1단계: 제목 전체 검색 (따옴표 포함)
        quoted_title = f'"{title}"'
        search_url = f"https://m.search.naver.com/search.naver?where=m_blog&query={quoted_title}"
        
        async with async_playwright() as p:
            # 리소스 차단 적용하여 속도 향상
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Linux; Android 10; SM-G981B)")
            page = await context.new_page()
            
            # 리소스 차단
            await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff2}", lambda route: route.abort())

            try:
                await page.goto(search_url, timeout=10000)
                # 결과 리스트 확인
                results = await page.locator("li.bx").all()
                
                found = False
                if results:
                    # 입력된 URL에서 logNo 추출
                    target_log_no = re.search(r'(\d+)$', url.strip("/")).group(1) if re.search(r'(\d+)$', url.strip("/")) else ""
                    
                    for res in results[:3]:
                        link_el = res.locator("a.api_txt_lines")
                        if await link_el.count() > 0:
                            href = await link_el.get_attribute("href")
                            if target_log_no in href:
                                found = True
                                break
                
                if found:
                    status = "✅ 정상 (검색 노출 중)"
                else:
                    if results:
                        status = "⚠️ 유사문서/누락 (제목은 있으나 내 글이 아님)"
                    else:
                        status = "❌ 완전 누락 (검색 결과 없음)"
                    
                return {"status": status, "url": url, "title": title}
            except Exception as e:
                return {"status": "오류", "error": str(e)}
            finally:
                await browser.close()

