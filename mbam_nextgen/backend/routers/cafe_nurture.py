from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import uuid

from ..database import get_db, NaverAccount, JoinedCafe, CafeSchedule, CafeManuscript, Advertiser, Agency, Distributor
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
    board_name: Optional[str] = ""   # 게시판이름 제거 — 카페만 매핑(선택사항)
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
    # 게시글 부스트: 대상 글 URL(없으면 방문만), 조회수/좋아요 수행 여부
    target_post_url: Optional[str] = None
    do_view: Optional[bool] = True
    do_like: Optional[bool] = True
    visit_interval_min: Optional[int] = 30

class TargetPostRequest(BaseModel):
    urls: List[str]
    account_ids: List[str]
    keyword: str
    delay_min: int = 30
    delay_max: int = 60
    ai_provider: str = "claude"
    use_tethering: bool = False   # USB 테더링으로 계정마다 IP 로테이션
    comment_content: str = ""     # 직접 입력 댓글(여러 줄=후보). 비면 AI 자동 생성
    do_like: bool = True          # 댓글과 함께 게시글 좋아요(공감)도 누름

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
    user_id = get_user_id(current_user)
    # 소유권 검증: 본인 계정에 속한 카페만 삭제 가능 (IDOR 방지)
    cafe = db.query(JoinedCafe).join(NaverAccount, JoinedCafe.account_id == NaverAccount.id).filter(
        JoinedCafe.id == cafe_id, NaverAccount.user_id == user_id
    ).first()
    if not cafe:
        raise HTTPException(status_code=404, detail="카페 정보를 찾을 수 없습니다.")
    db.delete(cafe)
    db.commit()
    return {"message": "카페 정보가 삭제되었습니다."}

# --- 3. Scheduling ---
@router.post("/schedules", summary="육성 스케줄 추가")
async def add_schedule(req: ScheduleCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    # 소유권 검증: 본인 계정/카페로만 스케줄 등록 가능 (IDOR 방지)
    acc = db.query(NaverAccount).filter(NaverAccount.id == req.account_id, NaverAccount.user_id == user_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    cafe = db.query(JoinedCafe).join(NaverAccount, JoinedCafe.account_id == NaverAccount.id).filter(
        JoinedCafe.id == req.cafe_id, NaverAccount.user_id == user_id
    ).first()
    if not cafe:
        raise HTTPException(status_code=404, detail="카페 정보를 찾을 수 없습니다.")
    new_sch = CafeSchedule(
        user_id=user_id,
        account_id=req.account_id,
        cafe_id=req.cafe_id,
        schedule_time=req.schedule_time,
        content_category=req.content_category,
        content_item_id=req.content_item_id,
        content_item_title=req.content_item_title,
        post_count_per_day=req.post_count_per_day,
        post_qty_per_time=req.post_qty_per_time,
        target_post_url=(req.target_post_url or None),
        do_view=1 if req.do_view else 0,
        do_like=1 if req.do_like else 0,
        visit_interval_min=int(req.visit_interval_min or 30)
    )
    db.add(new_sch)
    db.commit()
    db.refresh(new_sch)
    # 실행 중인 스케줄러에 즉시 등록 (서버 재시작 없이 바로 예약 동작)
    try:
        from mbam_nextgen.services.scheduler_service import scheduler_service
        scheduler_service.add_cafe_schedule_job(new_sch.id, new_sch.schedule_time)
    except Exception as e:
        print(f"[cafe_nurture] 스케줄러 즉시 등록 실패: {e}")
    return {"message": "스케줄이 등록되었습니다.", "id": new_sch.id}

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
                "target_post_url": getattr(s, "target_post_url", None),
                "do_view": getattr(s, "do_view", 1),
                "do_like": getattr(s, "do_like", 1),
                "visit_interval_min": getattr(s, "visit_interval_min", 30),
                "is_active": s.is_active
            })
    return result

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    # 소유권 검증: 본인 스케줄만 삭제 가능 (IDOR 방지)
    sch = db.query(CafeSchedule).filter(CafeSchedule.id == schedule_id, CafeSchedule.user_id == user_id).first()
    if sch:
        db.delete(sch)
        db.commit()
        try:
            from mbam_nextgen.services.scheduler_service import scheduler_service
            scheduler_service.remove_cafe_schedule_job(schedule_id)
        except Exception:
            pass
    return {"message": "스케줄이 삭제되었습니다."}

# --- 3.5 일괄 발행용 저장 원고 (계정별 원고 + 카페/게시판) ---
class ManuscriptItem(BaseModel):
    account_id: Optional[str] = ""   # 발행 네이버 아이디
    cafe_url: Optional[str] = ""
    board_name: Optional[str] = ""
    title: Optional[str] = ""
    content: Optional[str] = ""

class ManuscriptBulkSave(BaseModel):
    items: List[ManuscriptItem]
    replace: Optional[bool] = True   # True면 기존 저장분을 비우고 새로 저장

@router.post("/manuscripts", summary="계정별 원고(+카페/게시판) 일괄 저장")
async def save_manuscripts(req: ManuscriptBulkSave, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    if req.replace:
        # 이번에 저장하는 계정만 교체(다른 계정의 기존 저장 원고는 보존)
        acc_ids = list({(it.account_id or "") for it in req.items if it.account_id})
        if acc_ids:
            db.query(CafeManuscript).filter(
                CafeManuscript.user_id == user_id,
                CafeManuscript.status == "saved",
                CafeManuscript.account_id.in_(acc_ids),
            ).delete(synchronize_session=False)
    saved = 0
    for it in req.items:
        if not (it.content or "").strip():
            continue
        db.add(CafeManuscript(
            user_id=user_id, account_id=it.account_id, cafe_url=it.cafe_url,
            board_name=it.board_name, title=(it.title or "")[:200], content=it.content, status="saved",
        ))
        saved += 1
    db.commit()
    return {"message": f"{saved}개 원고가 저장되었습니다.", "count": saved}

@router.get("/manuscripts", summary="저장된 일괄 발행 원고 목록")
async def list_manuscripts(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    rows = db.query(CafeManuscript).filter(CafeManuscript.user_id == user_id, CafeManuscript.status == "saved").order_by(CafeManuscript.created_at.asc()).all()
    return [{"id": r.id, "account_id": r.account_id, "cafe_url": r.cafe_url, "board_name": r.board_name,
             "title": r.title, "content": r.content, "created_at": r.created_at.isoformat() if r.created_at else None} for r in rows]

class ManuscriptEdit(BaseModel):
    cafe_url: Optional[str] = None
    board_name: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None

@router.put("/manuscripts/{manuscript_id}", summary="저장 원고 수정")
async def update_manuscript(manuscript_id: str, req: ManuscriptEdit, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    m = db.query(CafeManuscript).filter(CafeManuscript.id == manuscript_id, CafeManuscript.user_id == user_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="원고를 찾을 수 없습니다.")
    if req.cafe_url is not None: m.cafe_url = req.cafe_url
    if req.board_name is not None: m.board_name = req.board_name
    if req.title is not None: m.title = req.title[:200]
    if req.content is not None: m.content = req.content
    db.commit()
    return {"message": "수정되었습니다."}

@router.delete("/manuscripts/{manuscript_id}", summary="저장 원고 삭제")
async def delete_manuscript(manuscript_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    m = db.query(CafeManuscript).filter(CafeManuscript.id == manuscript_id, CafeManuscript.user_id == user_id).first()
    if m:
        db.delete(m)
        db.commit()
    return {"message": "삭제되었습니다."}

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
            use_tethering=req.use_tethering,
            comment_content=req.comment_content,
            do_like=req.do_like,
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
