import asyncio
import os
import time
import hashlib
import hmac
import base64
import requests
from dotenv import load_dotenv

# .env 파일 경로 명시적 지정
load_dotenv("mbam_nextgen/.env")

async def test_keyword_volume():
    customer_id = os.getenv("NAVER_CUSTOMER_ID")
    access_license = os.getenv("NAVER_ACCESS_LICENSE")
    secret_key = os.getenv("NAVER_SECRET_KEY")

    print(f"Customer ID: {customer_id}")
    print(f"Access License: {access_license[:10]}...")
    print(f"Secret Key: {secret_key[:10]}...")

    if not all([customer_id, access_license, secret_key]):
        print("API keys not found in .env")
        return

    def generate_signature(timestamp, method, uri, secret):
        message = f"{timestamp}.{method}.{uri}"
        hash = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha256)
        return base64.b64encode(hash.digest()).decode('utf-8')

    timestamp = str(int(time.time() * 1000))
    method = "GET"
    uri = "/keywordstool"
    keywords = ["동래맛집", "부산맛집"]
    kw_param = ",".join(keywords)
    
    signature = generate_signature(timestamp, method, uri, secret_key)
    headers = {
        "X-Timestamp": timestamp,
        "X-API-KEY": access_license,
        "X-Customer": str(customer_id),
        "X-Signature": signature
    }
    
    url = f"https://api.naver.com{uri}?keywords={kw_param}"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {res.status_code}")
        if res.status_code == 200:
            print("Success!")
            print(res.json())
        else:
            print(f"Error: {res.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    asyncio.run(test_keyword_volume())
