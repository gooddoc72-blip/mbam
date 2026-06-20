from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import asyncio
from mbam_nextgen.orchestrator import WorkflowOrchestrator, task_logger

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

async def run_communication_task(task_id: str, req: CommunicationRequest):
    task_status_store[task_id] = {"status": "running", "logs": ["소통&이웃 작업이 시작되었습니다."]}
    
    def log(msg: str):
        print(f"[{task_id}] {msg}")
        task_status_store[task_id]["logs"].append(msg)
        
    task_logger.set(log)

    try:
        orchestrator = WorkflowOrchestrator()
        account_id = req.naver_id if req.naver_id else "unknown_account"
        
        safe_limit = min(req.limit, 10)
        
        log("소통&이웃 워크플로우를 시작합니다...")
        result = await orchestrator.execute_engagement_workflow(
            account_id=account_id,
            keyword=req.target_keyword,
            limit=safe_limit,
            do_like=req.enable_like,
            do_comment=req.enable_comment,
            comment_msg=req.comment_message,
            do_neighbor=req.enable_neighbor,
            neighbor_msg=req.neighbor_message,
            min_delay=req.min_delay,
            max_delay=req.max_delay
        )
        
        if "error" in result and not result.get("success", True):
            log(f"⚠️ 소통&이웃 워크플로우 실패: {result.get('error')}")
        else:
            log(f"✅ 소통&이웃 순회 완료! (총 {len(result)}곳 방문)")
            
        task_status_store[task_id]["status"] = "completed"
        
    except Exception as e:
        log(f"오류 발생: {str(e)}")
        task_status_store[task_id]["status"] = "failed"


@router.post("/")
async def trigger_communication(req: CommunicationRequest, background_tasks: BackgroundTasks):
    import uuid

    if req.limit > 10:
        req.limit = 10 # 어뷰징 방지 하드 리밋
        
    task_id = str(uuid.uuid4())
    background_tasks.add_task(run_communication_task, task_id, req)
    return {
        "success": True, 
        "message": "소통 작업이 백그라운드에서 시작되었습니다.", 
        "task_id": task_id
    }

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in task_status_store:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_status_store[task_id]
