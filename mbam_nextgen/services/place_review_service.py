import asyncio
from playwright.async_api import async_playwright
import re
import os
import httpx

class PlaceReviewService:
    """네이버 스마트플레이스 리뷰 수집 서비스"""
    
    def __init__(self):
        self.download_dir = "mbam_nextgen/temp_clips/images"
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    async def collect_reviews(self, place_url: str) -> dict:
        """방문자 리뷰 및 사진 수집 (Apollo State 기반, 초고속/우회)"""
        print(f"[PlaceReview] 플레이스 리뷰 수집 시작: {place_url}")
        
        # Ensure URL points to the review/visitor tab
        if "/home" in place_url:
            review_url = place_url.replace("/home", "/review/visitor")
        elif "/review/visitor" not in place_url:
            review_url = place_url.rstrip("/") + "/review/visitor"
        else:
            review_url = place_url

        try:
            import json
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            
            async with httpx.AsyncClient() as client:
                res = await client.get(review_url, headers=headers, timeout=15.0)
                if res.status_code != 200:
                    raise Exception(f"Failed to fetch page, status: {res.status_code}")
                
                html = res.text
                # 단순 ({.*?}); 는 첫 '};'에서 잘려 JSON이 깨짐 → naver_crawler와 동일하게 ';\s*window.'로 종결 앵커
                match = re.search(r'window\.__APOLLO_STATE__\s*=\s*({.*?});\s*window\.', html, re.DOTALL)
                if not match:
                    raise Exception("Apollo State not found in HTML (Bot detection or DOM change)")
                
                data = json.loads(match.group(1))
                reviews = []
                image_urls = []
                
                for key, value in data.items():
                    if key.startswith('VisitorReview:') and 'body' in value:
                        if value.get('body'):
                            reviews.append(value.get('body'))
                        if value.get('thumbnail'):
                            image_urls.append(value.get('thumbnail'))
                            
                # 이미지 다운로드 (최대 5개 활용)
                downloaded_paths = []
                for i, url in enumerate(image_urls[:5]):
                    try:
                        # 썸네일 해상도 높이기 (쿼리 파라미터 조정)
                        high_res_url = re.sub(r'type=[a-zA-Z0-9_]+', 'type=w640', url)
                        if 'type=' not in high_res_url and '?' not in high_res_url:
                            high_res_url += '?type=w640'
                        elif 'type=' not in high_res_url:
                            high_res_url += '&type=w640'
                            
                        img_res = await client.get(high_res_url, timeout=10.0)
                        if img_res.status_code == 200:
                            path = os.path.join(self.download_dir, f"review_img_{i}.jpg")
                            with open(path, "wb") as f:
                                f.write(img_res.content)
                            downloaded_paths.append(path)
                    except Exception as e:
                        print(f"[PlaceReview] 이미지 다운로드 실패: {e}")

                return {
                    "success": True,
                    "reviews": reviews[:40], # 최대 40개
                    "image_paths": downloaded_paths
                }
        except Exception as e:
            print(f"[PlaceReview] 리뷰 수집 중 오류: {e}")
            return {"success": False, "error": str(e)}
