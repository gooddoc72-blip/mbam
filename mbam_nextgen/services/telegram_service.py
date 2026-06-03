import os
import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    async def send_message(self, text: str, reply_markup: Dict[str, Any] = None) -> bool:
        if not self.base_url or not self.chat_id:
            logger.warning("Telegram API keys are not configured.")
            return False

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(f"{self.base_url}/sendMessage", json=payload, timeout=10.0)
                if res.status_code == 200:
                    return True
                else:
                    logger.error(f"Telegram send failed: {res.status_code} - {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Telegram send exception: {str(e)}")
            return False

    async def send_keyword_approval_request(self, keywords: List[str]):
        """
        관심 등록된 글감 리스트를 전송하고, 승인 버튼을 함께 띄워줍니다.
        """
        if not keywords:
            return

        text = "📝 <b>[자동 수집 완료] 관심 글감 리스트</b>\n\n"
        text += "수집된 글감을 바탕으로 자동 포스팅을 진행할 키워드를 선택해주세요.\n\n"
        
        for idx, kw in enumerate(keywords, 1):
            text += f"{idx}. {kw}\n"
            
        text += "\n원하시는 키워드를 클릭하시면 자동으로 포스팅이 시작됩니다."
        
        # Inline Keyboard 구성 (한 줄에 하나씩 버튼 배치)
        inline_keyboard = []
        for kw in keywords:
            inline_keyboard.append([
                {
                    "text": f"✅ '{kw}' 포스팅 시작",
                    "callback_data": f"post_blog:{kw}"
                }
            ])

        reply_markup = {
            "inline_keyboard": inline_keyboard
        }

        return await self.send_message(text, reply_markup)
