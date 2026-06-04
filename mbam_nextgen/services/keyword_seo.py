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

SPAM_WORDS = {'특가', '무료배송', '이벤트', '신상', '쿠폰', '할인', '정품', '사은품', '당일발송'}

def clean_and_tokenize(keyword: str) -> List[str]:
    """형태소 분리 및 필터링"""
    cleaned = re.sub(r'[!?,\[\]\(\)\{\}\<\>~*]', ' ', keyword)
    if not kiwi:
        return [w for w in cleaned.split() if w not in SPAM_WORDS]
    
    tokens = kiwi.tokenize(cleaned)
    valid_tokens = []
    for t in tokens:
        if t.tag.startswith('N') or t.tag == 'SL':
            word = t.form
            if word not in SPAM_WORDS and not re.fullmatch(r'\d{4}', word):
                valid_tokens.append(word)
    return valid_tokens

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
    
    params = {
        "hintKeywords": keyword,
        "showDetail": "1"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://api.naver.com/keywordstool", headers=headers, params=params, timeout=5.0)
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
    # Sort by frequency in top 10
    top_10_tokens = [item[0] for item in token_counts.most_common(20)]
    
    ad_keywords = await fetch_search_ad_keywords(seed)
    long_tail = []
    
    if ad_keywords:
        # Sort by monthly search volume (PC + Mobile). '< 10' is returned as string by Naver, handle safely
        def parse_vol(v):
            if isinstance(v, str):
                if v == '< 10': return 10
                return int(v.replace(',', ''))
            return v
            
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
        "long_tail_keywords": long_tail_tokens,
        "valid_tokens_pool": list(dict.fromkeys(top_10_tokens + long_tail_tokens)), # preserve order, remove duplicates
        "message": "분석 완료 (Top 10 기반)"
    }
