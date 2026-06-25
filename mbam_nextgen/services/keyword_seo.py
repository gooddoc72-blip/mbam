import os
import re
import httpx
import asyncio
from typing import List, Dict, Any
from collections import Counter

import hmac
import hashlib
import base64
import time

# Optional Kiwi for NLP
try:
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
except ImportError:
    kiwi = None

SPAM_WORDS = {'특가', '무료배송', '이벤트', '신상', '쿠폰', '할인', '정품', '사은품', '당일발송', '무료', '배송', '포장', '용량', '박스', '주문', '사이즈'}

def clean_and_tokenize(keyword: str) -> List[str]:
    """형태소 분리 및 필터링"""
    cleaned = re.sub(r'[!?,\[\]\(\)\{\}\<\>~*]', ' ', keyword)
    if not kiwi:
        return [w for w in cleaned.split() if w not in SPAM_WORDS and len(w) > 1]
    
    tokens = kiwi.tokenize(cleaned)
    valid_tokens = []
    for t in tokens:
        # 일반명사(NNG), 고유명사(NNP), 영어(SL)
        if t.tag in ('NNG', 'NNP', 'SL'):
            word = t.form
            # 1글자 단어(g, 개, x 등) 제거 및 스팸/숫자만 있는 단어 제거
            if len(word) > 1 and word not in SPAM_WORDS and not re.fullmatch(r'\d+', word):
                valid_tokens.append(word)
    return valid_tokens

async def fetch_autocomplete_related(keyword: str) -> List[str]:
    """네이버 자동완성(ac.search.naver.com)으로 실제 연관 검색어 수집. API 키 불필요(무료)."""
    import urllib.parse
    url = f"https://ac.search.naver.com/nx/ac?q={urllib.parse.quote(keyword)}&con=1&rev=4&q_enc=UTF-8&st=100"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6.0)
            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])
                if items:
                    return [it[0] for it in items[0] if it][:15]
    except Exception as e:
        print("autocomplete error:", e)
    return []


async def fetch_top_10_shopping(keyword: str) -> List[str]:
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return []

    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    url = f"https://openapi.naver.com/v1/search/shop.json?query={keyword}&display=10&start=1"
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers=headers, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                titles = [re.sub(r'<[^>]+>', '', item['title']) for item in data.get('items', [])]
                return titles
        except Exception as e:
            print("Error fetching top 10:", e)
    return []

async def fetch_search_ad_keywords(keyword: str) -> List[Dict[str, Any]]:
    customer_id = os.environ.get("NAVER_CUSTOMER_ID")
    access_license = os.environ.get("NAVER_ACCESS_LICENSE")
    secret_key = os.environ.get("NAVER_SECRET_KEY")
    
    if not customer_id or not access_license or not secret_key:
        return []
        
    timestamp = str(int((time.time()) * 1000))
    method = "GET"
    uri = "/keywordstool"
    message = f"{timestamp}.{method}.{uri}"
    signature = base64.b64encode(hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).digest()).decode()
    
    headers = {
        "X-Timestamp": timestamp,
        "X-API-KEY": access_license,
        "X-Customer": customer_id,
        "X-Signature": signature
    }
    
    # Naver Ad API rejects spaces. Split by space to get individual words, then comma-separate them (max 5 hints)
    words = list(dict.fromkeys(keyword.split()))[:5]
    query_keyword = ",".join(words)
    
    params = {
        "hintKeywords": query_keyword,
        "showDetail": "1"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://api.naver.com/keywordstool", headers=headers, params=params, timeout=5.0, follow_redirects=True)
            if resp.status_code == 200:
                data = resp.json()
                return data.get('keywordList', [])
        except Exception as e:
            print("Error fetching search ad keywords:", e)
    return []

async def analyze_seo_keyword(seed: str) -> Dict[str, Any]:
    titles = await fetch_top_10_shopping(seed)
    
    all_tokens = []
    for title in titles:
        tokens = clean_and_tokenize(title)
        all_tokens.extend(tokens)
        
    seed_tokens = clean_and_tokenize(seed)
    # Remove seed tokens from the pool to get pure related tokens
    filtered_tokens = [t for t in all_tokens if t not in seed_tokens]
    
    token_counts = Counter(filtered_tokens)
    # 1. 넉넉하게 후보군 추출
    raw_top_tokens = [item[0] for item in token_counts.most_common(100)]
    
    ad_keywords = await fetch_search_ad_keywords(seed)
    long_tail = []
    
    top_10_tokens = raw_top_tokens[:20] # 기본값
    
    if ad_keywords:
        ad_keywords_list = [k['relKeyword'] for k in ad_keywords]
        
        # 2. 연관검색어에 속해 있는 진짜 '검색 키워드'만 필터링 (g, kg, 개, ml 등 스팸/단위 제거)
        valid_tokens = [t for t in raw_top_tokens if any(t in kw for kw in ad_keywords_list)]
        
        if valid_tokens:
            top_10_tokens = valid_tokens[:20]

    if ad_keywords:
        # Sort by monthly search volume (PC + Mobile). '< 10' is returned as string by Naver, handle safely
        def parse_vol(v):
            if isinstance(v, str):
                if '<' in v:  # '< 10', '<10' 등
                    return 10
                try:
                    return int(float(v.replace(',', '').strip()))
                except (ValueError, TypeError):
                    return 0
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return 0
            
        for k in ad_keywords:
            vol = parse_vol(k.get('monthlyPcQcCnt', 0)) + parse_vol(k.get('monthlyMobileQcCnt', 0))
            if vol > 0:
                long_tail.append({"keyword": k['relKeyword'], "volume": vol})
                
        # Sort by volume ascending (lowest first = long tail)
        long_tail.sort(key=lambda x: x['volume'])
        # Take the top 10 lowest volume ones that are somewhat relevant
        long_tail_tokens = [item['keyword'] for item in long_tail[:20]]
    else:
        # Fallback to top 10 tokens if no AD API
        long_tail_tokens = top_10_tokens
        
    return {
        "seed_keyword": seed,
        "seed_tokens": seed_tokens,
        "top_10_titles": titles,
        "top_10_tokens": top_10_tokens,
        "valid_tokens_pool": list(dict.fromkeys(top_10_tokens + long_tail_tokens)), # preserve order, remove duplicates
        "related_keywords_count": len(ad_keywords) if ad_keywords else 0,
        "message": "분석 완료 (Top 10 기반)"
    }
