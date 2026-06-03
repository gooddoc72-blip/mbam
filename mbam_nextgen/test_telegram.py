import os
import requests
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv("mbam_nextgen/.env")

bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

if not bot_token or not chat_id:
    print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in .env")
    exit(1)

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

payload = {
    "chat_id": chat_id,
    "text": "🤖 [시스템 알림] 텔레그램 연동 테스트 메시지입니다!\n\n이 메시지를 받으셨다면, 봇 연동이 성공적으로 완료된 것입니다. 이제 글감 자동 수집 및 푸시 알림 기능을 본격적으로 구현할 수 있습니다.",
    "parse_mode": "HTML"
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    print("Success: Message sent successfully!")
else:
    print(f"Fail (Status Code: {response.status_code})")
    print(response.text)
