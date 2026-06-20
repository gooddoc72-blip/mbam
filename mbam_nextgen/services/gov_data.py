import json
import os
import asyncio
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

DATA_PATH = "mbam_nextgen/data"
os.makedirs(DATA_PATH, exist_ok=True)

class GovDataCollector:
    """
    [Infrastructure] 정부지원 데이터 수집기
    1차: 보조금24 API (data.go.kr 키 사용)
    2차: 샘플 데이터 폴백
    """

    SAMPLE_DATA = [
        {"id": "GOV001", "title": "소상공인 긴급경영안정자금", "category": "공공서비스", "source": "샘플",
         "summary": "매출 감소 소상공인 대상 최대 2,000만원 긴급 경영안정자금 지원. 연 2% 저금리 융자.",
         "target": "매출 감소 소상공인", "amount": "최대 2,000만원", "deadline": "2026-06-30",
         "keywords": ["소상공인", "긴급자금", "경영안정"]},
        {"id": "EDU001", "title": "인공지능을 위한 R과 Python", "category": "K-MOOC 강좌", "source": "서강대학교",
         "summary": "AI 데이터 분석을 위한 기초 프로그래밍 강의",
         "target": "전 국민", "professor": "이윤동", "deadline": "26.04.16~26.07.19",
         "keywords": ["AI", "Python", "R"]},
        {"id": "HOU001", "title": "고양장항 A-4블록 행복주택", "category": "행복주택", "source": "LH",
         "summary": "경기 고양시 장항동 일원 행복주택 입주자 모집",
         "target": "청년, 신혼부부", "amount": "임대료 저렴", "deadline": "2026-05-25",
         "keywords": ["행복주택", "고양", "LH"]},
    ]

    CATEGORIES = {
        "소상공인24 (sbiz24)": "소상공인 맞춤형 정부지원사업 및 정책자금",
        "기업마당 (Bizinfo)": "중소기업/소상공인 지원사업 정보",
        "창업진흥원 (K-startup)": "예비창업자 및 스타트업 육성 사업",
        "복지로 (Bokjiro)": "생애주기별 맞춤형 복지 서비스 및 수당",
        "K-MOOC 강좌": "교육/강좌 정보",
        "공연/행사": "문화 예술 행사 정보",
        "공공서비스": "정부/지자체 제공 서비스 및 지원금",
        "네이버 뉴스 (많이 본 뉴스)": "검색량 급상승/많이 본 뉴스",
        "고캠핑": "전국 캠핑장 정보",
        "생태관광": "전국 생태 관광지 정보",
        "반려동물 동반여행": "애견 동반 가능 여행지 및 시설",
        "웰니스": "치유/힐링/웰니스 관광 정보",
        "국민임대": "국민임대주택 모집공고",
        "행복주택": "행복주택 입주자 모집공고",
        "공공임대 모집공고": "SH/LH 공공임대 통합 공고"
    }

    def __init__(self):
        # Env는 상단에서 이미 로드됨
        self.api_key = self._load_api_key()
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.cache_file = os.path.join(DATA_PATH, "gov_data_cache.json")
        from .soul import SoulRewriter
        self.soul = SoulRewriter()

    def _load_api_key(self) -> str:
        env_path = "mbam_nextgen/.env"
        if os.path.exists(env_path):
            with open(env_path, encoding='utf-8') as f:
                for line in f:
                    if line.startswith("GOV_DATA_API_KEY="):
                        return line.strip().split("=", 1)[1]
        return None

    async def fetch_data(self, category: str = "공공서비스") -> list:
        """데이터 수집 (선택된 카테고리에 맞춰 수집)"""
        
        # 1. 크롤러 방식 우선 (오류 방지 위해 AI보다 위로 배치)
        if category == "네이버 뉴스 (많이 본 뉴스)":
            result = self._fetch_naver_trending_news()
            if result:
                return result
                
        if category == "소상공인24 (sbiz24)":
            result = self._fetch_official_blog_crawler("marketagency", category, "소상공인시장진흥공단")
            if result: return result
            
        if category == "기업마당 (Bizinfo)":
            result = self._fetch_official_blog_crawler("bizinfo1357", category, "기업마당 공식")
            if result: return result

        # 2. AI 방식 (크롤러가 없는 카테고리이거나 크롤러 실패 시 폴백)
        if self.gemini_key:
            print(f"[GovData] [AI] Gemini AI를 통해 [{category}] 리서치 시작...")
            data = await self._fetch_via_ai(category)
            if data:
                print(f"[GovData] [OK] {category} 정보 {len(data)}건 확보")
                return data

        # 3. 보조금24 API 방식
        if category == "공공서비스" and self.api_key and HAS_REQUESTS:
            result = self._fetch_subsidy24()
            if result:
                return result

        print(f"[GovData] [Fallback] {category} 샘플 데이터 사용")
        # 매칭 샘플이 없을 때 전체 SAMPLE_DATA를 반환하면 다른 카테고리 데이터가 섞여 노출됨 → 빈 리스트 반환
        return [d for d in self.SAMPLE_DATA if d.get("category") == category]

    async def _fetch_via_ai(self, category: str) -> list:
        """Gemini AI에게 특정 카테고리의 공공 데이터 조사를 요청"""
        
        description = self.CATEGORIES.get(category, "정부/지자체 정보")
        
        # 카테고리별 특수 필드 및 소스 강조 정의
        custom_fields = ""
        source_focus = "대한민국 공공기관"
        
        if category == "소상공인24 (sbiz24)":
            source_focus = "소상공인24 (sbiz24.kr)"
            custom_fields = '"application_period": "신청기간", "support_target": "지원대상(예: 매출액 3억 이하)",'
        elif category == "기업마당 (Bizinfo)":
            source_focus = "기업마당 (bizinfo.go.kr)"
            custom_fields = '"application_period": "접수기간", "region": "지원지역",'
        elif category == "창업진흥원 (K-startup)":
            source_focus = "K-Startup (k-startup.go.kr)"
            custom_fields = '"biz_stage": "창업단계(예비/초기/도약)", "biz_area": "분야",'
        elif category == "복지로 (Bokjiro)":
            source_focus = "복지로 (bokjiro.go.kr)"
            custom_fields = '"benefit_type": "지원형태(현금/바우처 등)",'
        elif category == "K-MOOC 강좌":
            source_focus = "K-MOOC (kmooc.kr)"
            custom_fields = '"professor": "교수명", "period": "수강신청기간",'
        elif "임대" in category or "주택" in category:
            source_focus = "LH 청약플러스 또는 SH"
            custom_fields = '"location": "지역", "supply_type": "공급유형",'

        prompt = f"""
        현재 년도는 2026년입니다. 과거(2023년 등) 데이터는 절대 포함하지 마세요. 반드시 **2026년 기준 최신 데이터**만 조사하세요.
        **{source_focus}**를 중심으로 **{category}({description})** 관련 실제 공공데이터 20건을 조사하여 JSON으로 출력해주세요.
        
        데이터 선정 및 정렬 기준은 반드시 다음 **우선순위**를 따르세요:
        [1순위] 최신순/혜택: 공고일이 가장 최근이거나, 지원 혜택(금액/조건)이 매우 우수한 정보 (priority: 1)
        [2순위] 트렌드: 현재 시즌이나 사회적 이슈로 검색량이 급증하는 정보 (priority: 2)
        [3순위] 긴급성: 신청 마감일이 7일 이내로 임박한 정보 (priority: 3)
        
        응답은 반드시 아래 형식을 지킨 순수 JSON 배열이어야 합니다:
        [
          {{
            "id": "AI_{category}_001",
            "title": "정보의 제목 (반드시 2026년 기준 공고만 작성할 것)",
            "category": "{category}",
            "source": "{source_focus}",
            {custom_fields}
            "summary": "핵심 내용 한 문장 요약",
            "target": "지원 대상 조건",
            "deadline": "YYYY-MM-DD 또는 상시",
            "priority": 1, 
            "keywords": ["키워드1", "키워드2"]
          }}
        ]
        """
        try:
            response_text = await self.soul.generate_content(prompt)
            json_str = re.sub(r'```json\s*|```', '', response_text).strip()
            start = json_str.find('[')
            end = json_str.rfind(']') + 1
            if start != -1 and end > start:
                json_str = json_str[start:end]
            
            data = json.loads(json_str)
            if isinstance(data, list):
                return data
        except Exception as e:
            print(f"[GovData] [Error] AI [{category}] 리서치 실패: {e}")
        return None

    def _fetch_official_blog_crawler(self, blog_id: str, category: str, source_name: str) -> list:
        """공식 네이버 블로그 크롤러 (소상공인진흥공단, 기업마당 등)"""
        if not HAS_REQUESTS or not HAS_BS4:
            return None
            
        print(f"[GovData] [Scraping] {source_name} 공식 블로그 데이터 수집 중...")
        url = f"https://m.blog.naver.com/PostList.naver?blogId={blog_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            items = []
            # 모바일 네이버 블로그 포스트 리스트 (thmb_list 클래스 등)
            post_list = soup.select(".list_item") or soup.select(".card_item") or soup.select("li.item")
            
            if not post_list:
                # RSS Fallback if mobile HTML parsing fails
                return self._fetch_official_blog_rss(blog_id, category, source_name)
                
            for idx, post in enumerate(post_list[:15]):
                title_node = post.select_one(".title") or post.select_one(".tit")
                if not title_node: continue
                title = title_node.text.strip()
                
                link_node = post.select_one("a")
                href = link_node.get("href", "") if link_node else ""
                full_link = f"https://m.blog.naver.com{href}" if href.startswith("/") else href
                
                # 우선순위 부여 (1: 최신글 3개, 2: 나머지)
                priority = 1 if idx < 3 else 2
                
                item = {
                    "id": f"CRAWL_{blog_id}_{idx}",
                    "title": title,
                    "category": category,
                    "source": source_name,
                    "summary": f"{source_name} 공식 채널의 최신 업데이트 소식입니다.",
                    "target": "해당 공고 참조",
                    "deadline": "상시 (상세내용 참조)",
                    "priority": priority,
                    "keywords": [source_name, title.split()[0]],
                    "url": full_link
                }
                items.append(item)
            
            if items:
                print(f"[GovData] [Scraping] {source_name} {len(items)}건 완료.")
                return items
            else:
                return self._fetch_official_blog_rss(blog_id, category, source_name)
                
        except Exception as e:
            print(f"[GovData] [Error] {source_name} 크롤링 실패: {e}")
            return None

    def _fetch_official_blog_rss(self, blog_id: str, category: str, source_name: str) -> list:
        """공식 블로그 RSS 크롤링 (HTML 파싱 실패 시 백업)"""
        url = f"https://rss.blog.naver.com/{blog_id}.xml"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200: return None
            
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text.encode('utf-8'))
            items = []
            
            for idx, item in enumerate(root.findall('.//item')):
                title = item.find('title').text if item.find('title') is not None else "제목 없음"
                link = item.find('link').text if item.find('link') is not None else ""
                
                priority = 1 if idx < 3 else 2
                
                items.append({
                    "id": f"RSS_{blog_id}_{idx}",
                    "title": title,
                    "category": category,
                    "source": source_name,
                    "summary": f"{source_name} 공식 채널 최신 업데이트",
                    "target": "공고문 참조",
                    "deadline": "상세내용 참조",
                    "priority": priority,
                    "keywords": [source_name, title.split()[0] if title else "공고"],
                    "url": link
                })
                if len(items) >= 15: break
            
            if items:
                print(f"[GovData] [Scraping] {source_name} RSS {len(items)}건 완료.")
            return items
        except Exception as e:
            print(f"[GovData] [Error] {source_name} RSS 실패: {e}")
            return None

    def _fetch_naver_trending_news(self) -> list:
        """네이버 언론사별 가장 많이 본 뉴스 스크래핑"""
        if not HAS_REQUESTS or not HAS_BS4:
            print("[GovData] [Error] requests 또는 BeautifulSoup 라이브러리가 없습니다.")
            return None
            
        print("[GovData] [Scraping] 네이버 랭킹 뉴스 수집 중...")
        url = "https://news.naver.com/main/ranking/popularDay.naver"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            items = []
            boxes = soup.select(".rankingnews_box")
            
            for box in boxes:
                # 언론사 이름
                press_node = box.select_one(".rankingnews_name")
                press_name = press_node.text.strip() if press_node else "네이버 뉴스"
                
                # 상위 1~3위 뉴스
                news_list = box.select("ul > li")
                for idx, news in enumerate(news_list):
                    a_tag = news.select_one(".list_content a")
                    if not a_tag: continue
                    
                    title = a_tag.text.strip()
                    link = a_tag.get("href", "")
                    
                    # 랭킹 번호 (예: 1위)
                    rank_node = news.select_one(".list_ranking_num")
                    rank = rank_node.text.strip() if rank_node else str(idx + 1)
                    
                    # 이미 너무 많이 수집하지 않게 각 언론사별 1위만 수집하거나 전체 다 수집.
                    # 여기서는 전체 다 (보통 5개씩) 하되 1위~2위 정도만 높은 priority 부여
                    priority = 1 if rank in ["1", "2"] else 2
                    
                    item = {
                        "id": f"NAVER_{hash(link) % 100000}",
                        "title": title,
                        "category": "네이버 뉴스 (많이 본 뉴스)",
                        "source": press_name,
                        "summary": f"{press_name} 분야 {rank}위 뉴스입니다. 검색량이 높은 이슈입니다.",
                        "target": "전체",
                        "deadline": "상시",
                        "priority": priority,
                        "keywords": [press_name, "인기뉴스", title.split()[0]],
                        "url": link
                    }
                    items.append(item)
                    
                    # 수집 개수 제한 (총 100개 이하로)
                    if len(items) >= 60:
                        break
                if len(items) >= 60:
                    break
                    
            print(f"[GovData] [Scraping] {len(items)}개의 뉴스 수집 완료.")
            return items
        except Exception as e:
            print(f"[GovData] [Error] 네이버 뉴스 스크래핑 실패: {e}")
            return None


    def _fetch_subsidy24(self) -> list:
        """보조금24 API 호출 - 실제 데이터 수집"""
        print("[GovData] [API] 보조금24 API에서 수집 중...")
        url = "https://apis.data.go.kr/1741000/Subsidy24/getSubsidy24"
        params = {
            "serviceKey": self.api_key,
            "pageNo": 1,
            "numOfRows": 50,
            "type": "json"
        }
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                items = []
                if isinstance(data, dict):
                    body = data.get("response", {}).get("body", {})
                    if body:
                        items = body.get("items", body.get("item", []))
                        if isinstance(items, dict):
                            items = items.get("item", [])
                    if not items: items = data.get("data", [])

                if isinstance(items, list) and len(items) > 0:
                    result = self._transform(items)
                    if result: return result
            return None
        except Exception as e:
            print(f"[GovData] [Error] API 연결 실패: {e}")
            return None

    def _transform(self, items: list) -> list:
        """API 응답을 표준 형식으로 변환"""
        result = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict) or "서비스명" not in str(item): continue
            
            title = (item.get("서비스명") or item.get("svcNm") or item.get("title"))
            summary = (item.get("서비스목적요약") or item.get("svcPurps") or item.get("summary") or "")

            result.append({
                "id": f"API_{idx:03d}_{hash(str(title)) % 10000}",
                "title": str(title),
                "category": "공공서비스",
                "source": "정부 API",
                "summary": str(summary)[:300],
                "target": str(item.get("선정기준", "")),
                "amount": str(item.get("지원내용", "")),
                "deadline": str(item.get("신청기한", "상시")),
                "keywords": [str(title).split()[0]] if title else []
            })
        return result

    def _classify(self, text: str) -> str:
        """카테고리 자동 분류"""
        rules = {
            "공공서비스": ["지원금", "복지", "자금", "수당"],
            "K-MOOC 강좌": ["강좌", "강의", "학습", "수강"],
            "행복주택": ["행복주택", "임대주택"],
            "고캠핑": ["캠핑", "야영"],
        }
        for cat, kws in rules.items():
            if any(kw in text for kw in kws):
                return cat
        return "기타"

    async def fetch_all_categories_batch(self):
        """전체 카테고리의 데이터를 일괄 수집하여 캐시 저장"""
        print(f"[GovData] [Batch] 전용 일괄 수집 시작... ({len(self.CATEGORIES)}개 카테고리)")
        
        results = {}
        for category in self.CATEGORIES.keys():
            try:
                data = await self.fetch_data(category)
                if data:
                    self.save_cache(category, data)
                    results[category] = len(data)
                    print(f"[GovData] [Batch] {category}: {len(data)}건 저장 완료")
                # AI API 속도 제한 방지를 위한 짧은 대기
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[GovData] [Batch] {category} 수집 실패: {e}")
        
        # 통합 업데이트 일시 기록
        batch_info = {
            "last_batch_run": datetime.now().isoformat(),
            "summary": results
        }
        with open(os.path.join(DATA_PATH, "batch_info.json"), "w", encoding="utf-8") as f:
            json.dump(batch_info, f, ensure_ascii=False, indent=2)
            
        return results

    def _get_cache_path(self, category: str) -> str:
        # 파일명에 안전한 이름으로 변환 (공백/특수문자 제거)
        safe_name = re.sub(r'[^a-zA-Z0-9가-힣]', '_', category)
        return os.path.join(DATA_PATH, f"cache_{safe_name}.json")

    def save_cache(self, category: str, data: list):
        path = self._get_cache_path(category)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "category": category,
                "updated": datetime.now().isoformat(),
                "items": data
            }, f, ensure_ascii=False, indent=2)

    def load_cache(self, category: str) -> list:
        path = self._get_cache_path(category)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f).get("items", [])
            except: return []
        return []

    def get_cache_time(self, category: str) -> str:
        path = self._get_cache_path(category)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    dt_str = json.load(f).get("updated", "없음")
                    if dt_str != "없음":
                        dt = datetime.fromisoformat(dt_str)
                        return dt.strftime("%Y-%m-%d %H:%M")
            except: return "없음"
        return "없음"
