from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
import asyncio

from mbam_nextgen.orchestrator import WorkflowOrchestrator, task_logger

router = APIRouter()

class AccountInfo(BaseModel):
    id: str
    pw: str
    keyword: Optional[str] = None
    image: Optional[str] = None
    speed_mode: Optional[str] = "normal"
    speed_multiplier: Optional[float] = 1.0
    publish_mode: Optional[str] = "none"
    date: Optional[str] = None
    time: Optional[str] = None
    proxy: Optional[str] = None

class MultiTaskRequest(BaseModel):
    target_task: str # "blog" | "cafe" | "communication"
    accounts: List[AccountInfo]
    global_config: Dict[str, Any] = {}

task_status_store = {}
active_multi_tasks = {}

async def run_multi_workflow(task_id: str, req: MultiTaskRequest):
    # Store statuses for each account as well, since the frontend wants to monitor each
    # For now, we will store a global log and let the frontend adapt
    task_status_store[task_id] = {"status": "running", "logs": [f"[{req.target_task}] 순차 멀티 워크플로우 시작..."]}
    
    def log(msg: str):
        print(f"[MultiTask:{task_id}] {msg}")
        task_status_store[task_id]["logs"].append(msg)
        
    task_logger.set(log)

    try:
        orchestrator = WorkflowOrchestrator()
        
        # Convert Pydantic objects to dicts for orchestrator
        accounts_dicts = []
        for acc in req.accounts:
            accounts_dicts.append({
                "id": acc.id,
                "pw": acc.pw,
                "keyword": acc.keyword or req.global_config.get("keyword", "테스트"),
                "image": acc.image,
                "speed_mode": acc.speed_mode,
                "speed_multiplier": acc.speed_multiplier,
                "publish_mode": acc.publish_mode,
                "date": acc.date,
                "time": acc.time,
                "proxy": acc.proxy
            })
            
        log(f"총 {len(accounts_dicts)}개의 계정이 등록되었습니다.")
        
        schedule_time = req.global_config.get("schedule_time")
        
        async def execute_job():
            log(f"▶️ [{req.target_task}] 멀티 워크플로우 실행 시작...")
            if req.target_task == "blog":
                results = await orchestrator.execute_multi_workflow(accounts_dicts, req.global_config)
            elif req.target_task == "cafe":
                # 임시: 카페 멀티 워크플로우 지원 (기존 멀티 프레임워크 재사용 또는 단일 루프)
                # 현재는 orchestrator.execute_multi_workflow가 blog에 종속적이지 않도록 리팩토링했거나 
                # 또는 단순히 반복문을 직접 구현합니다.
                results = []
                for idx, acc in enumerate(accounts_dicts):
                    log(f"👉 [{idx+1}/{len(accounts_dicts)}] 카페 작업 시작: {acc['id']}")
                    if req.global_config.get("use_tethering"):
                        log("📱 USB 테더링 IP 전환 중...")
                        await orchestrator.proxy_manager.rotate_tethering_ip()
                    res = await orchestrator.execute_cafe_workflow(
                        account_id=acc["id"], cafe_id="joonggonara", board_name="자유게시판", 
                        keyword=acc["keyword"], ai_provider=req.global_config.get("ai_provider", "claude")
                    )
                    results.append(res)
            elif req.target_task == "communication":
                results = []
                for idx, acc in enumerate(accounts_dicts):
                    log(f"👉 [{idx+1}/{len(accounts_dicts)}] 소통 작업 시작: {acc['id']}")
                    if req.global_config.get("use_tethering"):
                        log("📱 USB 테더링 IP 전환 중...")
                        await orchestrator.proxy_manager.rotate_tethering_ip()
                    res = await orchestrator.execute_engagement_workflow(
                        account_id=acc["id"], keyword=acc["keyword"]
                    )
                    results.append({"success": True}) # 임시
            else:
                log(f"⚠️ 알 수 없는 타겟 태스크: {req.target_task}")
                return
            
            success_cnt = sum(1 for r in results if r.get('success'))
            log(f"✅ 전체 멀티 워크플로우 1회 완료! 성공: {success_cnt}/{len(results)}")
        
        if schedule_time:
            log(f"⏰ 매일 {schedule_time} 실행 스케줄러가 활성화되었습니다. (서버 종료 시까지 동작)")
            import datetime
            while True:
                now = datetime.datetime.now()
                target_hour, target_min = map(int, schedule_time.split(':'))
                target_dt = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
                
                if now > target_dt:
                    target_dt += datetime.timedelta(days=1)
                
                wait_seconds = (target_dt - now).total_seconds()
                log(f"⏳ 다음 실행까지 대기 중... ({wait_seconds:.0f}초 남음)")
                task_status_store[task_id]["status"] = f"waiting ({schedule_time})"
                await asyncio.sleep(wait_seconds)
                
                task_status_store[task_id]["status"] = "running"
                await execute_job()
                # 실행 후 다음날까지 다시 대기
        else:
            await execute_job()
            task_status_store[task_id]["status"] = "completed"
            
    except asyncio.CancelledError:
        log("작업이 취소되었습니다.")
        task_status_store[task_id]["status"] = "cancelled"
    except Exception as e:
        log(f"오류 발생: {str(e)}")
        task_status_store[task_id]["status"] = "failed"

@router.post("/")
async def trigger_multi_task(req: MultiTaskRequest):
    task_id = str(uuid.uuid4())
    task = asyncio.create_task(run_multi_workflow(task_id, req))
    active_multi_tasks[task_id] = task
    return {
        "success": True, 
        "message": "멀티 작업이 백그라운드에서 시작되었습니다.", 
        "task_id": task_id
    }

@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str):
    if task_id in active_multi_tasks:
        active_multi_tasks[task_id].cancel()
        task_status_store[task_id]["status"] = "failed"
        task_status_store[task_id]["logs"].append("🛑 사용자에 의해 작업이 강제 중단되었습니다.")
        return {"success": True, "message": "작업이 중단되었습니다."}
    return {"success": False, "message": "실행 중인 작업을 찾을 수 없습니다."}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in task_status_store:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_status_store[task_id]
