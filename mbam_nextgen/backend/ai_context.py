"""AI 키 컨텍스트 주입 의존성 (BYOK).

AI 생성을 쓰는 라우터에 이 의존성을 걸면, 요청 사용자의 저장된 키를
ContextVar 에 세팅한다. SoulRewriter 는 그 키를 우선 사용(없으면 .env 서버키).
 - 설치형 고객: 본인 키 입력 → 본인 계정에 청구(운영자 비용 0)
 - 웹 고객: 키 미입력 → 서버키 사용 + (쿼터로 과금)
"""
from fastapi import Depends
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from mbam_nextgen.services.ai_keys import set_ai_keys


def setup_ai_context(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    from .models import UserAIKey
    uid = current_user.get("sub")
    keys = {}
    try:
        rec = db.query(UserAIKey).filter(UserAIKey.user_id == uid).first()
        if rec:
            keys = {"claude_key": rec.claude_key, "gemini_key": rec.gemini_key, "openai_key": rec.openai_key}
    except Exception:
        pass
    # 빈 값은 제외 → 그 항목은 서버 .env 키로 폴백
    set_ai_keys({k: v for k, v in keys.items() if v})
    return current_user
