import os
import time
import httpx
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

from mbam_nextgen.services.telegram_service import TelegramService
from mbam_nextgen.services.trend_scraper import TrendScraper

# .env 로드
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{bot_token}"
BACKEND_URL = "http://127.0.0.1:8000/api/auto_post/"

async def send_message(chat_id, text):
    async with httpx.AsyncClient() as client:
        await client.post(f"{API_URL}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        })

async def process_update(update):
    if "callback_query" in update:
        query = update["callback_query"]
        data = query.get("data", "")
        chat_id = query["message"]["chat"]["id"]
        
        if data.startswith("post_blog:"):
            keyword = data.split("post_blog:", 1)[1]
            
            # 사용자에게 확인 메시지 전송
            await send_message(chat_id, f"🚀 <b>'{keyword}'</b> 키워드로 블로그 자동 포스팅 작업을 시작합니다!\n(로컬 서버의 백그라운드에서 진행됩니다.)")
            
            # 백엔드 API 호출 (프론트엔드에서 호출하는 것과 동일하게)
            payload = {
                "target_type": "blog",
                "login_mode": "auto",
                "naver_id": os.getenv("NAVER_ID", ""), # 필요 시 env나 DB에서
                "naver_pw": os.getenv("NAVER_PW", ""),
                "post_mode": "ai_generate",
                "target_keyword": keyword,
                "title": "",
                "content": "",
                "publish_mode": "instant",
                "schedule_date": "",
                "schedule_time": "",
                "ai_provider": "claude",
                "images": []
            }
            
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    res = await client.post(BACKEND_URL, json=payload)
                    if res.status_code == 200:
                        await send_message(chat_id, f"✅ <b>'{keyword}'</b> 포스팅 작업이 서버 큐에 성공적으로 등록되었습니다.")
                    else:
                        await send_message(chat_id, f"❌ 작업 등록 실패: {res.status_code}\n{res.text}")
            except Exception as e:
                await send_message(chat_id, f"❌ 서버 연결 오류: {str(e)}")
        
        # 콜백 쿼리 응답 (버튼의 로딩 아이콘 제거)
        async with httpx.AsyncClient() as client:
            await client.post(f"{API_URL}/answerCallbackQuery", json={"callback_query_id": query["id"]})

async def daily_trend_job():
    """매일 아침 9시에 핫이슈 글감을 텔레그램으로 전송하는 스케줄러"""
    tg_service = TelegramService()
    last_sent_date = None
    
    print("[Poller] 📈 일일 트렌드 글감 자동 수집 스케줄러가 시작되었습니다.")
    
    while True:
        now = datetime.now()
        # 매일 오전 9시에 한 번씩 전송 (9:00 ~ 9:01 사이)
        if now.hour == 9 and now.minute == 0:
            today_str = now.strftime("%Y-%m-%d")
            if last_sent_date != today_str:
                print(f"[{now}] 핫이슈 글감 수집 및 전송 중...")
                topics = TrendScraper.get_today_hot_topics(limit=5)
                if topics:
                    await tg_service.send_keyword_approval_request(topics)
                    last_sent_date = today_str
                    print("✅ 일일 트렌드 전송 완료!")
        
        # 1분 주기로 체크
        await asyncio.sleep(60)

async def main():
    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN not found.")
        return

    print("Telegram Poller Started...")
    
    # 트렌드 스케줄러 백그라운드 실행
    asyncio.create_task(daily_trend_job())
    
    offset = None
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            try:
                params = {"timeout": 30}
                if offset:
                    params["offset"] = offset
                    
                response = await client.get(f"{API_URL}/getUpdates", params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        await process_update(update)
                else:
                    print(f"Error fetching updates: {response.status_code}")
                    await asyncio.sleep(5)
            except Exception as e:
                print(f"Poller Exception: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
