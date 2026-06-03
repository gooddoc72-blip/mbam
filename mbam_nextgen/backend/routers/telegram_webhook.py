import logging
from fastapi import APIRouter, Request, BackgroundTasks
from mbam_nextgen.orchestrator import WorkflowOrchestrator
from mbam_nextgen.services.telegram_service import TelegramService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    텔레그램에서 전송되는 콜백(버튼 클릭) 및 일반 메시지를 수신합니다.
    """
    try:
        data = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON"}

    # Inline Keyboard 버튼 클릭 이벤트 처리
    if "callback_query" in data:
        callback_query = data["callback_query"]
        callback_data = callback_query.get("data", "")
        chat_id = callback_query["message"]["chat"]["id"]
        
        logger.info(f"Received callback_data: {callback_data} from chat_id: {chat_id}")
        
        tg_service = TelegramService()

        # "post_blog:키워드" 형태 파싱
        if callback_data.startswith("post_blog:"):
            keyword = callback_data.split("post_blog:", 1)[1]
            
            # 사용자에게 확인 메시지 전송
            await tg_service.send_message(
                text=f"🚀 <b>'{keyword}'</b> 키워드로 블로그 포스팅 자동화를 시작합니다!\n\n(완료 시 다시 알림을 드립니다.)",
                reply_markup=None
            )
            
            # 백그라운드에서 오케스트레이터 실행 (수동 로그인 대기가 아닌 자동 로그인 모드라고 가정)
            # 여기서는 기본적으로 클로드, 자동 로그인 모드 설정으로 구동
            orchestrator = WorkflowOrchestrator()
            background_tasks.add_task(
                orchestrator.execute_blog_workflow,
                login_mode="auto",
                post_mode="ai_generate",
                target_keyword=keyword,
                title="",
                content="",
                ai_provider="claude",
                images=[]
            )

            # 텔레그램 서버에 Callback 응답 처리 (로딩 애니메이션 제거)
            # await tg_service._answer_callback_query(callback_query["id"]) # 필요한 경우 구현
            
    return {"status": "ok"}
