"""요청별 사용자 AI 키(BYOK) 컨텍스트.

각 사용자가 자신의 Claude/Gemini/OpenAI 키를 설정에 저장하면, 요청 처리 동안
ContextVar 에 담아 SoulRewriter 가 그 키를 우선 사용한다(없으면 .env 폴백).
→ 판매 시 각 고객의 생성 비용이 '그 고객 계정'에 청구되어 운영자 비용 노출이 사라진다.

asyncio.create_task 는 생성 시점의 ContextVar 컨텍스트를 복사하므로,
요청 핸들러(의존성)에서 set 해두면 백그라운드 작업(자동발행/소통)에도 그대로 전파된다.
"""
from contextvars import ContextVar
from typing import Optional

_ctx: ContextVar[Optional[dict]] = ContextVar("ai_keys", default=None)


def set_ai_keys(keys: Optional[dict]) -> None:
    _ctx.set(keys or {})


def get_ai_keys() -> dict:
    try:
        return _ctx.get() or {}
    except Exception:
        return {}
