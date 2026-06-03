import os
import asyncio
from dotenv import load_dotenv
from mbam_nextgen.services.telegram_service import TelegramService

load_dotenv("mbam_nextgen/.env")

async def test_send():
    tg_service = TelegramService()
    
    # 가상의 "관심 등록" 키워드 리스트
    test_keywords = [
        "강남역 맛집 추천",
        "신사동 카페",
        "2024년 SEO 트렌드"
    ]
    
    print(f"Sending approval request for {len(test_keywords)} keywords...")
    success = await tg_service.send_keyword_approval_request(test_keywords)
    
    if success:
        print("✅ 키워드 리스트 전송 완료! 텔레그램을 확인해보세요.")
    else:
        print("❌ 전송 실패.")

if __name__ == "__main__":
    asyncio.run(test_send())
