import urllib.request
import xml.etree.ElementTree as ET
from typing import List

class TrendScraper:
    """
    [Domain Service] 실시간 트렌드 키워드 수집기
    Google Trends RSS (한국 지역) 등을 파싱하여 핫이슈 키워드를 추출합니다.
    """
    
    @staticmethod
    def get_google_trends(limit: int = 5) -> List[str]:
        """구글 트렌드 일별 인기 급상승 검색어 추출"""
        url = "https://trends.google.co.kr/trending/rss?geo=KR"
        keywords = []
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                xml_data = response.read()
                
            root = ET.fromstring(xml_data)
            
            # RSS 구조: channel -> item -> title (여기에 검색어가 있음)
            for item in root.findall('./channel/item'):
                title = item.find('title')
                if title is not None and title.text:
                    keywords.append(title.text.strip())
                    if len(keywords) >= limit:
                        break
                        
        except Exception as e:
            print(f"[TrendScraper] 구글 트렌드 수집 실패: {e}")
            
        return keywords

    @staticmethod
    def get_today_hot_topics(limit: int = 5) -> List[str]:
        """오늘의 추천 글감 리스트 반환 (여러 소스 취합 가능)"""
        print("[TrendScraper] 오늘의 핫이슈 글감 수집 중...")
        trends = TrendScraper.get_google_trends(limit)
        
        # fallback
        if not trends:
            trends = ["오늘의 날씨", "국내 여행지 추천", "재테크 노하우", "맛집 탐방", "최신 IT 기기"]
            
        return trends[:limit]

# 테스트용 실행 코드
if __name__ == "__main__":
    topics = TrendScraper.get_today_hot_topics(5)
    print("오늘의 추천 글감:")
    for idx, topic in enumerate(topics):
        print(f"{idx+1}. {topic}")
