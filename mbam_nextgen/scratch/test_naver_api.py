import os
import time
import hashlib
import hmac
import base64
import requests

CUSTOMER_ID = "3944832"
API_KEY = "010000000007d68a1ad5b16f2833dfaa4946191ae6f6c6d314cda084207924592f3aaffc195"
SECRET_KEY = "AQAAAAB9aKGtWxbygz36pJRhka5vfY2j8u5BbHMWrYeul/hbdw=="

def generate_signature(timestamp, method, path, secret_key):
    message = f"{timestamp}.{method}.{path}"
    hash = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256)
    hash.hexdigest()
    return base64.b64encode(hash.digest()).decode("utf-8")

def get_header(method, path):
    timestamp = str(int(time.time() * 1000))
    signature = generate_signature(timestamp, method, path, SECRET_KEY)
    return {
        "X-Timestamp": timestamp,
        "X-API-KEY": API_KEY,
        "X-Customer": CUSTOMER_ID,
        "X-Signature": signature
    }

def get_keyword_volume(keyword):
    method = "GET"
    path = "/keywordstool"
    url = f"https://api.naver.com{path}?hintKeywords={keyword}&showDetail=1"
    
    headers = get_header(method, path)
    res = requests.get(url, headers=headers)
    
    if res.status_code == 200:
        data = res.json()
        if "keywordList" in data and len(data["keywordList"]) > 0:
            item = data["keywordList"][0]
            # Naver returns < 10 as string. We need to handle this.
            pc_cnt = item.get('monthlyPcQcCnt', 0)
            mo_cnt = item.get('monthlyMobileQcCnt', 0)
            
            try: pc_cnt = int(pc_cnt)
            except: pc_cnt = 10
            
            try: mo_cnt = int(mo_cnt)
            except: mo_cnt = 10
                
            return {
                "keyword": item.get('relKeyword'),
                "pc_volume": pc_cnt,
                "mo_volume": mo_cnt,
                "total_volume": pc_cnt + mo_cnt,
                "related_keywords": [k.get('relKeyword') for k in data["keywordList"][1:6]]
            }
        else:
            print("API returned 200 but no keywordList or it's empty:", data)
    else:
        print(f"API Error {res.status_code}: {res.text}")
    return None

if __name__ == "__main__":
    result = get_keyword_volume("동래맛집")
    print(result)
