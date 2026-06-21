from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

from ..database import get_db, NaverAccount, JoinedCafe, CafeSchedule, Advertiser, Agency, Distributor
from ..auth import get_current_user
from mbam_nextgen.orchestrator import WorkflowOrchestrator
from mbam_nextgen.backend.routers.auto_post import task_status_store, active_tasks as auto_post_active_tasks

router = APIRouter(prefix="/api/cafe-nurture", tags=["cafe_nurture"])

# --- Models ---
class AccountCreate(BaseModel):
    naver_id: str
    naver_pw: str

class AccountResponse(BaseModel):
    id: str
    naver_id: str
    status: str
    created_at: str

    class Config:
        orm_mode = True

class CafeCreate(BaseModel):
    account_id: str
    cafe_url: str
    board_name: str
    nickname: Optional[str] = None

class ScheduleCreate(BaseModel):
    account_id: str
    cafe_id: str
    schedule_time: str
    content_category: Optional[str] = None
    content_item_id: Optional[str] = None
    content_item_title: Optional[str] = None
    post_count_per_day: Optional[int] = 1
    post_qty_per_time: Optional[int] = 1

class TargetPostRequest(BaseModel):
    urls: List[str]
    account_ids: List[str]
    keyword: str
    delay_min: int = 30
    delay_max: int = 60
    ai_provider: str = "claude"

# --- Utils ---
def get_user_id(current_user: dict):
    return current_user.get("sub") # Email or Login ID

# --- 1. Account Management ---
@router.post("/accounts", summary="네이버 계정 추가")
async def add_account(req: AccountCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    
    # Check duplicate
    existing = db.query(NaverAccount).filter(NaverAccount.user_id == user_id, NaverAccount.naver_id == req.naver_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 등록된 계정입니다.")
        
    new_acc = NaverAccount(
        user_id=user_id,
        naver_id=req.naver_id,
        naver_pw=req.naver_pw # In production, encrypt this
    )
    db.add(new_acc)
    db.commit()
    db.refresh(new_acc)
    return {"message": "계정이 추가되었습니다.", "id": new_acc.id}

@router.get("/accounts", summary="저장된 네이버 계정 목록 조회")
async def get_accounts(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    accounts = db.query(NaverAccount).filter(NaverAccount.user_id == user_id).all()
    
    result = []
    for acc in accounts:
        cafes = db.query(JoinedCafe).filter(JoinedCafe.account_id == acc.id).all()
        result.append({
            "id": acc.id,
            "naver_id": acc.naver_id,
            "status": acc.status,
            "cafes": [{"id": c.id, "cafe_url": c.cafe_url, "board_name": c.board_name} for c in cafes]
        })
    return result

@router.delete("/accounts/{account_id}")
async def delete_account(account_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    acc = db.query(NaverAccount).filter(NaverAccount.id == account_id, NaverAccount.user_id == user_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    
    db.delete(acc)
    db.commit()
    return {"message": "계정이 삭제되었습니다."}

# --- 2. Cafe Mapping ---
@router.post("/cafes", summary="가입 카페 매핑 추가")
async def add_joined_cafe(req: CafeCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    acc = db.query(NaverAccount).filter(NaverAccount.id == req.account_id, NaverAccount.user_id == user_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
        
    new_cafe = JoinedCafe(
        account_id=req.account_id,
        cafe_url=req.cafe_url,
        board_name=req.board_name,
        nickname=req.nickname
    )
    db.add(new_cafe)
    db.commit()
    return {"message": "카페 정보가 저장되었습니다."}

@router.delete("/cafes/{cafe_id}")
async def delete_joined_cafe(cafe_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    cafe = db.query(JoinedCafe).filter(JoinedCafe.id == cafe_id).first()
    if not cafe:
        raise HTTPException(status_code=404, detail="카페 정보를 찾을 수 없습니다.")
    db.delete(cafe)
    db.commit()
    return {"message": "카페 정보가 삭제되었습니다."}

# --- 3. Scheduling ---
@router.post("/schedules", summary="육성 스케줄 추가")
async def add_schedule(req: ScheduleCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    new_sch = CafeSchedule(
        user_id=user_id,
        account_id=req.account_id,
        cafe_id=req.cafe_id,
        schedule_time=req.schedule_time,
        content_category=req.content_category,
        content_item_id=req.content_item_id,
        content_item_title=req.content_item_title,
        post_count_per_day=req.post_count_per_day,
        post_qty_per_time=req.post_qty_per_time
    )
    db.add(new_sch)
    db.commit()
    # TODO: Reload APScheduler
    return {"message": "스케줄이 등록되었습니다."}

@router.get("/schedules")
async def get_schedules(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    schedules = db.query(CafeSchedule).filter(CafeSchedule.user_id == user_id).all()
    
    result = []
    for s in schedules:
        acc = db.query(NaverAccount).filter(NaverAccount.id == s.account_id).first()
        cafe = db.query(JoinedCafe).filter(JoinedCafe.id == s.cafe_id).first()
        if acc and cafe:
            result.append({
                "id": s.id,
                "account_id": s.account_id,
                "naver_id": acc.naver_id,
                "cafe_id": s.cafe_id,
                "cafe_url": cafe.cafe_url,
                "board_name": cafe.board_name,
                "schedule_time": s.schedule_time,
                "content_category": s.content_category,
                "content_item_id": s.content_item_id,
                "content_item_title": s.content_item_title,
                "post_count_per_day": s.post_count_per_day,
                "post_qty_per_time": s.post_qty_per_time,
                "is_active": s.is_active
            })
    return result

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    sch = db.query(CafeSchedule).filter(CafeSchedule.id == schedule_id).first()
    if sch:
        db.delete(sch)
        db.commit()
    return {"message": "스케줄이 삭제되었습니다."}

# --- 4. Targeted Auto Comment Trigger ---
# Now uses task_status_store from auto_post.py

async def run_multi_target_task(task_id: str, req: TargetPostRequest, accounts_data: list):
    task_status_store[task_id] = {"status": "running", "logs": ["[다중 타겟팅] 작업을 시작합니다..."]}
    
    def log(msg: str):
        print(f"[{task_id}] {msg}")
        task_status_store[task_id]["logs"].append(msg)
        
    try:
        orchestrator = WorkflowOrchestrator()
        
        # This will be handled inside a specialized orchestrator method in the future.
        # For now, let's call a new method `execute_targeted_multi_cafe_workflow`
        
        result = await orchestrator.execute_targeted_multi_cafe_workflow(
            accounts_data=accounts_data,
            target_urls=req.urls,
            keyword=req.keyword,
            ai_provider=req.ai_provider,
            delay_min=req.delay_min,
            delay_max=req.delay_max,
            logger_func=log
        )
        
        task_status_store[task_id]["status"] = "completed"
        log("✅ 모든 타겟 다중 댓글 작업이 완료되었습니다!")
        
    except Exception as e:
        log(f"❌ 오류 발생: {str(e)}")
        task_status_store[task_id]["status"] = "failed"

@router.post("/trigger-targeted", summary="다중 아이디로 타겟 게시글 댓글 작업 시작")
async def trigger_targeted(req: TargetPostRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    import asyncio
    user_id = get_user_id(current_user)
    
    accounts_data = []
    for acc_id in req.account_ids:
        acc = db.query(NaverAccount).filter(NaverAccount.id == acc_id, NaverAccount.user_id == user_id).first()
        if acc:
            accounts_data.append({"id": acc.naver_id, "pw": acc.naver_pw})
            
    if not accounts_data:
        raise HTTPException(status_code=400, detail="선택된 계정이 없거나 권한이 없습니다.")
        
    task_id = str(uuid.uuid4())
    task = asyncio.create_task(run_multi_target_task(task_id, req, accounts_data))
    auto_post_active_tasks[task_id] = task
    
    return {"success": True, "task_id": task_id, "message": "다중 계정 타겟 작업이 시작되었습니다."}

@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str):
    if task_id in auto_post_active_tasks:
        auto_post_active_tasks[task_id].cancel()
        task_status_store[task_id]["status"] = "failed"
        task_status_store[task_id]["logs"].append("🛑 사용자에 의해 작업이 강제 중단되었습니다.")
        return {"success": True, "message": "작업이 중단되었습니다."}
    return {"success": False, "message": "실행 중인 작업을 찾을 수 없습니다."}

@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in task_status_store:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_status_store[task_id]
