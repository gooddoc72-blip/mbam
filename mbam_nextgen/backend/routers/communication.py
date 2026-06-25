from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import asyncio
from mbam_nextgen.orchestrator import WorkflowOrchestrator, task_logger
from mbam_nextgen.backend.quota import consume_generation_quota

router = APIRouter()

class CommunicationRequest(BaseModel):
    login_mode: str # "manual" | "auto"
    naver_id: Optional[str] = None
    naver_pw: Optional[str] = None
    
    target_keyword: str
    limit: int = 10
    
    min_delay: int = 30
    max_delay: int = 120
    
    enable_neighbor: bool = False
    neighbor_message: Optional[str] = ""
    enable_like: bool = False
    enable_comment: bool = False
    comment_message: Optional[str] = ""

task_status_store = {}

async def run_communication_task(task_id: str, req: CommunicationRequest, stop_event: asyncio.Event):
    store = task_status_store[task_id]

    def log(msg: str):
        print(f"[{task_id}] {msg}")
        store["logs"].append(msg)

    task_logger.set(log)

    try:
        orchestrator = WorkflowOrchestrator()
        account_id = req.naver_id if req.naver_id else "unknown_account"

        safe_limit = min(req.limit, 10)

        log("소통&이웃 워크플로우를 시작합니다...")
        result = await orchestrator.execute_engagement_workflow(
            account_id=account_id,
            keyword=req.target_keyword,
            account_pw=req.naver_pw,
            limit=safe_limit,
            do_like=req.enable_like,
            do_comment=req.enable_comment,
            comment_msg=req.comment_message,
            do_neighbor=req.enable_neighbor,
            neighbor_msg=req.neighbor_message,
            min_delay=req.min_delay,
            max_delay=req.max_delay,
            stop_event=stop_event,
        )
        
        if isinstance(result, dict) and result.get("error"):
            log(f"⚠️ 소통&이웃 워크플로우 실패: {result.get('error')}")
        else:
            visited = result if isinstance(result, list) else []
            ok = sum(1 for r in visited if r.get("success"))
            if stop_event.is_set():
                log(f"⏹ 중지됨 (방문 {len(visited)}곳 / 성공 {ok}곳)")
            elif not visited:
                log("⚠️ 방문할 블로그를 찾지 못했습니다. (검색 결과 없음 또는 로그인 필요)")
            else:
                log(f"✅ 소통&이웃 순회 완료! (방문 {len(visited)}곳 / 성공 {ok}곳)")

        store["status"] = "stopped" if stop_event.is_set() else "completed"

    except asyncio.CancelledError:
        log("⏹ 작업이 취소되었습니다.")
        store["status"] = "stopped"
        raise
    except Exception as e:
        log(f"오류 발생: {str(e)}")
        store["status"] = "failed"
    finally:
        store.pop("task", None)


@router.post("")
@router.post("/")
async def trigger_communication(req: CommunicationRequest, _q: dict = Depends(consume_generation_quota)):
    import uuid

    if req.limit > 10:
        req.limit = 10 # 어뷰징 방지 하드 리밋

    task_id = str(uuid.uuid4())
    stop_event = asyncio.Event()
    task_status_store[task_id] = {
        "status": "running",
        "logs": ["소통&이웃 작업이 시작되었습니다."],
        "stop_event": stop_event,
    }
    task = asyncio.create_task(run_communication_task(task_id, req, stop_event))
    task_status_store[task_id]["task"] = task
    return {
        "success": True,
        "message": "소통 작업이 백그라운드에서 시작되었습니다.",
        "task_id": task_id
    }

@router.post("/stop/{task_id}")
async def stop_task(task_id: str):
    store = task_status_store.get(task_id)
    if not store:
        raise HTTPException(status_code=404, detail="Task not found")
    ev = store.get("stop_event")
    if ev:
        ev.set()  # 협조적 중지: 현재 동작 마무리 후 다음 단계에서 멈춤
    return {"success": True, "message": "중지를 요청했습니다. 진행 중인 단계가 끝나면 멈춥니다."}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    store = task_status_store.get(task_id)
    if not store:
        raise HTTPException(status_code=404, detail="Task not found")
    # 직렬화 불가 객체(stop_event/task) 제외하고 반환
    return {k: v for k, v in store.items() if k not in ("stop_event", "task")}
