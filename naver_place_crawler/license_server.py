from fastapi import FastAPI
from pydantic import BaseModel
import json
import os

app = FastAPI()

# 승인된 HWID를 저장할 간단한 JSON 파일 경로
DB_FILE = "authorized_hwids.json"

class AuthRequest(BaseModel):
    hwid: str

def load_authorized_hwids():
    if not os.path.exists(DB_FILE):
        return []
    with open(DB_FILE, "r") as f:
        return json.load(f)

@app.post("/verify")
async def verify_hwid(req: AuthRequest):
    """
    클라이언트(크롤러)가 보낸 HWID가 승인된 목록에 있는지 확인합니다.
    """
    authorized_list = load_authorized_hwids()
    
    if req.hwid in authorized_list:
        return {"authorized": True, "message": "승인된 기기입니다."}
    else:
        # 미승인 기기 접속 시도 기록을 남길 수 있습니다.
        print(f"[경고] 미승인 기기 접근 시도: {req.hwid}")
        return {"authorized": False, "message": "승인되지 않은 기기입니다."}

# 사용 방법:
# 1. pip install fastapi uvicorn
# 2. uvicorn license_server:app --host 0.0.0.0 --port 8000
# 3. authorized_hwids.json 파일을 생성하고 ["사용자의_HWID_입력"] 형태로 저장해두면 됩니다.
