import os
import time
import hmac
import hashlib
import base64
import requests
import asyncio
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

class KeywordBrain:
    """
    [L1. The Brain]
    네이버 검색광고 API를 사용하여 실제 황금 키워드를 분석합니다.
    """
    
    def __init__(self):
        self.api_url = "https://api.naver.com"
        self.access_license = os.getenv("NAVER_ACCESS_LICENSE")
        self.secret_key = os.getenv("NAVER_CLIENT_SECRET")
        self.customer_id = os.getenv("NAVER_CLIENT_ID") # Client ID often used as Customer ID in Ad API

    def _generate_signature(self, timestamp: str, method: str, path: str):
        """네이버 검색광고 API 호출을 위한 시그니처 생성"""
        message = f"{timestamp}.{method}.{path}"
        hash = hmac.new(self.secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
        return base64.b64encode(hash).decode('utf-8')

    def _get_headers(self, method: str, path: str):
        timestamp = str(int(time.time() * 1000))
        return {
            "Content-Type": "application/json; charset=UTF-8",
            "X-Timestamp": timestamp,
            "X-API-KEY": self.access_license,
            "X-Customer": self.customer_id,
            "X-Signature": self._generate_signature(timestamp, method, path)
        }

    async def get_keyword_stats(self, keywords: List[str]) -> List[Dict]:
        """네이버 광고 API를 통해 키워드의 월간 검색량 조회"""
        if not self.access_license or not self.secret_key:
            print("[Brain] API 키가 설정되지 않아 가상 데이터를 반환합니다.")
            return [{"keyword": k, "monthly_search": 1000} for k in keywords]

        path = "/keywordstool"
        params = {"hintKeywords": ",".join(keywords), "showDetail": "1"}
        
        try:
            # Note: In a real environment, we would use aiohttp for true async
            response = await asyncio.to_thread(
                requests.get, 
                f"{self.api_url}{path}", 
                params=params, 
                headers=self._get_headers("GET", path)
            )
            return response.json().get("keywordList", [])
        except Exception as e:
            print(f"[Brain] 키워드 조회 중 오류: {e}")
            return []

    async def find_golden_keywords(self, seed: str) -> List[Dict]:
        """
        검색량은 많고 발행량은 적은 키워드 발굴
        1. 광고 API로 연관 키워드 및 검색량 확보
        2. 블로그 검색 API로 발행량 확보 (추후 구현)
        3. 비율 계산 후 추천
        """
        stats = await self.get_keyword_stats([seed])
        # 실제 로직에서는 여기서 발행량(doc_count)을 조회하여 ratio 계산
        return stats
