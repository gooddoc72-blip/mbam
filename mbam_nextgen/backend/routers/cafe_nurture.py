from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Form, Body
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
    # 댓글 작성 텀 — 화면에서 조정한다. 짧을수록 네이버가 도배로 잡을 위험이 커진다.
    delay_min: int = 30           # 같은 계정이 다음 게시글로 넘어가기 전 대기(초)
    delay_max: int = 60
    account_delay_min: int = 10   # 다음 계정으로 넘어가기 전 대기(초)
    account_delay_max: int = 30
    ai_provider: str = "claude"
    use_tethering: bool = False   # USB 테더링으로 계정마다 IP 로테이션
    comment_content: str = ""     # 직접 입력 댓글(여러 줄=후보). 비면 AI 자동 생성
    do_like: bool = True          # 댓글과 함께 게시글 좋아요(공감)도 누름
    # 등록된 프록시 풀로 계정마다 IP를 바꿔가며 댓글/공감.
    #   None  = [설정 > IP 방식] 을 따름 (ip_mode 가 proxy 일 때만 사용)
    #   True  = 설정과 무관하게 등록된 프록시 풀을 사용
    #   False = 프록시 사용 안 함
    use_proxy: Optional[bool] = None
    # 미리보기에서 확인·수정한 댓글 {게시글URL: [댓글, ...]}.
    # 있으면 그 URL 에는 AI 를 다시 돌리지 않고 이 문장을 그대로 쓴다.
    comments_by_url: Optional[dict] = None


class CommentPreviewRequest(BaseModel):
    """실행 전에 AI 댓글을 미리 만들어 보여주기 위한 요청.

    실제로 댓글을 달지 않는다. 게시글 본문만 읽어 후보 문장을 만들어 돌려주고,
    사용자가 화면에서 확인·수정한 뒤 그 문장으로 실행하게 한다.
    """
    urls: List[str]
    keyword: str = ""
    ai_provider: str = "claude"
    count: int = 3                 # URL 당 만들 후보 수(계정 수만큼 다양하게 쓰라고 여러 개)

# --- Utils ---
def get_user_id(current_user: dict):
    return current_user.get("sub") # Email or Login ID


def build_proxy_map(db, user_id: str, accounts_data: list, use_proxy) -> dict:
    """댓글/공감 작업용 계정별 프록시 배정표 {네이버ID: 프록시URL} 을 만든다.

    두 가지를 동시에 만족시켜야 한다.
      1) 계정 고정(sticky) — 같은 계정은 늘 같은 IP. 계정 IP 가 매번 튀면
         네이버가 이상 접속으로 잡는다. 그래서 해시(계정ID) 로 자리를 정한다.
      2) 겹치지 않게 — 여러 계정이 한 IP 에서 댓글을 달면 도배로 보인다.
         proxy_pool.pick 처럼 해시만 쓰면 충돌이 나서(4계정/3프록시 → IP 2개만 사용)
         남는 프록시가 놀게 되므로, 충돌 시 빈 자리로 밀어 넣는다(선형 탐사).

    결과는 (계정 목록, 프록시 목록) 이 같으면 항상 동일하다. 계정 수가 프록시 수보다
    많으면 한 바퀴 다 쓴 뒤 다시 처음부터 채우므로 공유는 최소한으로만 생긴다.
    """
    if use_proxy is False:
        return {}
    from mbam_nextgen.services import proxy_pool
    settings = proxy_pool.get_ip_settings(db, user_id)
    # use_proxy 가 None(미지정)이면 [설정 > IP 방식] 을 그대로 따른다.
    if use_proxy is None and settings.get("ip_mode") != "proxy":
        return {}
    pool = proxy_pool.list_active(db, user_id)
    if not pool:
        return {}

    import hashlib
    n = len(pool)

    # ⚠ 배정은 '이번에 선택한 계정' 이 아니라 '등록된 전체 계정' 기준으로 계산한다.
    #   선택한 계정만으로 계산하면, 고를 때마다 선형 탐사 결과가 달라져 같은 계정이
    #   다른 IP 를 받는다(실측: 계정 8·프록시 3에서 33~41% 가 바뀜).
    #   계정 IP 가 매번 튀면 네이버가 이상 접속으로 잡으므로, 계정 고정이 깨지면 안 된다.
    selected = {a.get("id") for a in accounts_data if a.get("id")}
    all_ids = {r[0] for r in db.query(NaverAccount.naver_id)
                                .filter(NaverAccount.user_id == user_id).all() if r[0]}
    all_ids |= selected                      # DB 에 없는 계정이 실려와도 배정은 해준다

    # 배정 순서를 계정ID 해시로 고정 — 목록 순서가 바뀌어도 결과가 같다.
    ordered = sorted(all_ids, key=lambda i: hashlib.md5(i.encode("utf-8")).hexdigest())
    taken = set()
    out = {}
    for account_id in ordered:
        if len(taken) >= n:
            taken.clear()          # 프록시를 다 썼으면 다음 바퀴 시작
        start = int(hashlib.md5(account_id.encode("utf-8")).hexdigest(), 16) % n
        for step in range(n):
            idx = (start + step) % n
            if idx not in taken:
                break
        taken.add(idx)
        if account_id not in selected:
            continue               # 자리만 차지시키고(고정 유지) 결과에는 넣지 않는다
        url = proxy_pool.to_url(proxy_pool.to_playwright(pool[idx]))
        if url:
            out[account_id] = url
    return out

# --- 1. Account Management ---
@router.post("/accounts", summary="네이버 계정 추가")
async def add_account(req: AccountCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    
    # Check duplicate
    existing = db.query(NaverAccount).filter(NaverAccount.user_id == user_id, NaverAccount.naver_id == req.naver_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="이미 등록된 계정입니다.")

    # 플랜별 네이버 계정 수 제한 (관리자 페이지에서 설정한 값)
    from ..limits import check_account_limit
    adv = db.query(Advertiser).filter(Advertiser.email == user_id).first()
    if adv:
        current_count = db.query(NaverAccount).filter(NaverAccount.user_id == user_id).count()
        check_account_limit(db, adv, current_count)

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

async def run_multi_target_task(task_id: str, req: TargetPostRequest, accounts_data: list,
                                proxy_map: dict = None):
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
            account_delay_min=req.account_delay_min,
            account_delay_max=req.account_delay_max,
            use_tethering=req.use_tethering,
            comment_content=req.comment_content,
            do_like=req.do_like,
            proxies=proxy_map or {},
            comments_by_url=req.comments_by_url or {},
            logger_func=log
        )
        
        task_status_store[task_id]["status"] = "completed"
        log("✅ 모든 타겟 다중 댓글 작업이 완료되었습니다!")
        
    except Exception as e:
        log(f"❌ 오류 발생: {str(e)}")
        task_status_store[task_id]["status"] = "failed"

class MatjipCollectRequest(BaseModel):
    place_url: Optional[str] = None
    keyword: Optional[str] = None


class MatjipGenJob(BaseModel):
    image_folder: str = ""
    source_data: str = ""
    place_name: str = ""
    keyword: str = ""
    sub_keywords: Optional[List[str]] = None  # 서브(연관) 키워드 — 본문에 자연스럽게 녹임
    post_type: str = "matjip"                 # matjip | keyword(일키 포스팅)


_PHOTO_EXTS = (".jpg", ".jpeg", ".png", ".webp")
MAX_PHOTOS = 10


async def _run_photo_generate(user_id: str, job_id: str, payload: dict):
    """설치형: 이 PC 가 직접 폴더 사진을 읽어 원고를 만든다.

    ⚠ 예전에는 모드와 상관없이 잡 큐에만 넣었는데, 설치본은 에이전트(agent.py)를
      동봉하지도 실행하지도 않는다(설치 폴더에 파일 자체가 없다). 그래서 잡을 가져갈
      주체가 없어 화면은 4분 30초를 기다린 뒤 '시간 초과'만 냈다.
      카페 순위추적에서 고친 것과 같은 문제다 — 로컬에서는 직접 실행한다.
    """
    import os
    import re as _re
    from mbam_nextgen.backend import jobs as jobsvc
    from mbam_nextgen.services.soul import SoulRewriter
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        folder = (payload.get("image_folder") or "").strip()
        paths = []
        if folder and os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(_PHOTO_EXTS):
                    paths.append(os.path.join(folder, f))
                if len(paths) >= MAX_PHOTOS:
                    break
        txt = await SoulRewriter().generate_matjip_with_photos(
            payload.get("source_data") or "", paths,
            place_name=payload.get("place_name") or "",
            keyword=payload.get("keyword") or "",
            sub_keywords=payload.get("sub_keywords") or [],
            post_type=payload.get("post_type") or "matjip")
        txt = _re.sub(r"(\*\*|~~|__)", "", txt or "").strip()
        if not txt:
            raise RuntimeError("AI 가 빈 원고를 돌려줬습니다. (API 키·잔액 확인)")
        title = (payload.get("place_name") or payload.get("keyword") or "카페글")
        title = f"{title} 방문 후기" if (payload.get("post_type") or "matjip") != "keyword" else title
        body = txt
        m = _re.match(r"^\s*(?:제목\s*[:：]\s*|#\s*|\[제목\]\s*)(.+)", body)
        if m:
            title = m.group(1).strip()
            body = body[m.end():].strip()
        jobsvc.complete_job(db, job_id, user_id, "done",
                            result={"success": True, "title": title, "content": body,
                                    "image_count": len(paths)})
    except Exception as e:
        try:
            jobsvc.complete_job(db, job_id, user_id, "error", error=str(e))
        except Exception:
            pass
        print(f"[photo_generate] 실패: {e}")
    finally:
        db.close()


@router.post("/matjip-generate-job", summary="사진+참고자료 원고 생성 (맛집·일키 공용)")
async def matjip_generate_job(req: MatjipGenJob, background: BackgroundTasks,
                              db: Session = Depends(get_db),
                              current_user: dict = Depends(get_current_user)):
    """클라우드면 내 PC 에이전트가 폴더 사진을 올려 처리하고, 설치형이면 이 PC 가 직접 만든다.
    어느 쪽이든 job_id 를 돌려주므로 프론트는 /api/agent/jobs/{id} 폴링만 하면 된다."""
    from mbam_nextgen.backend import jobs as jobsvc
    payload = {"image_folder": req.image_folder, "source_data": req.source_data,
               "place_name": req.place_name, "keyword": req.keyword,
               "sub_keywords": req.sub_keywords or [],
               "post_type": (req.post_type or "matjip")}
    user_id = get_user_id(current_user)
    job_id = jobsvc.enqueue_job(db, user_id, "matjip_generate", payload, priority=3)
    if not jobsvc.is_cloud_mode():
        # ⚠ asyncio.create_task 대신 BackgroundTasks — 응답을 보낸 뒤 본래 이벤트 루프에서 돌려준다.
        background.add_task(_run_photo_generate, user_id, job_id, payload)
    return {"success": True, "job_id": job_id}


@router.post("/matjip-generate", summary="맛집: 사진+리뷰로 원고 생성(Claude 비전+작성)")
async def matjip_generate(
    images: List[UploadFile] = File(default=[]),
    source_data: str = Form(""),
    place_name: str = Form(""),
    keyword: str = Form(""),
    sub_keywords: str = Form(""),   # 쉼표로 구분된 서브 키워드(에이전트가 멀티파트 문자열로 전송)
    post_type: str = Form("matjip"),  # matjip | keyword(일키 포스팅)
    current_user: dict = Depends(get_current_user),
):
    """에이전트가 폴더 사진을 멀티파트로 올리면, 클라우드(마스터 키)가 사진+리뷰를 한 번에 보고
    사진에 맞는 자리에 [이미지] 마커를 넣은 맛집 후기 원고를 생성해 반환한다."""
    import os, re, tempfile
    from mbam_nextgen.services.soul import SoulRewriter
    paths = []
    tmpdir = tempfile.mkdtemp(prefix="matjip_gen_")
    for i, f in enumerate(images or []):
        try:
            ext = os.path.splitext(f.filename or "")[1].lower() or ".jpg"
            p = os.path.join(tmpdir, f"img_{i}{ext}")
            with open(p, "wb") as out:
                out.write(await f.read())
            paths.append(p)
        except Exception:
            pass
    sub_list = [s.strip() for s in (sub_keywords or "").split(",") if s.strip()][:5]
    try:
        txt = await SoulRewriter().generate_matjip_with_photos(
            source_data, paths, place_name=place_name, keyword=keyword,
            sub_keywords=sub_list, post_type=post_type or "matjip")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"원고 생성 실패: {e}")
    txt = re.sub(r"(\*\*|~~|__)", "", txt or "").strip()
    title = (place_name or keyword or "카페글")
    if (post_type or "matjip") != "keyword":
        title += " 방문 후기"
    body = txt
    m = re.match(r"^\s*(?:제목\s*[:：]\s*|#\s*|\[제목\]\s*)(.+)", body)
    if m:
        title = m.group(1).strip()
        body = body[m.end():].strip()
    return {"success": True, "title": title, "content": body, "image_count": len(paths)}


@router.post("/matjip-collect", summary="맛집 소재 수집(플레이스 리뷰+블로그 후기)")
async def matjip_collect(req: MatjipCollectRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from mbam_nextgen.backend import jobs as jobsvc
    place_url = (req.place_url or "").strip()
    keyword = (req.keyword or "").strip()
    if not place_url and not keyword:
        raise HTTPException(status_code=400, detail="플레이스 URL 또는 키워드를 입력하세요.")
    payload = {"place_url": place_url, "keyword": keyword}
    from mbam_nextgen.services.matjip_service import collect_matjip_source
    if jobsvc.is_cloud_mode():
        # 1순위: 서버에서 직접 수집 시도. 플레이스 방문자 리뷰는 데이터센터 IP 에서도 httpx 로
        #        수집 가능(브라우저 불필요) → 플레이스 URL 만 있으면 에이전트 없이 바로 채워진다.
        if place_url:
            try:
                import asyncio
                res = await asyncio.wait_for(
                    collect_matjip_source(place_url, keyword, browser_ok=False), timeout=40)
                if (res or {}).get("source_data"):
                    return {"success": True, "mode": "inline", "source_data": res["source_data"]}
            except Exception:
                pass  # 차단/실패 → 아래 에이전트로 폴백
        # 2순위: 서버가 못 하면(플레이스 URL 없음/차단, 또는 블로그 후기까지 필요) 로컬 에이전트 잡으로 적재.
        job_id = jobsvc.enqueue_job(db, get_user_id(current_user), "matjip_collect", payload, priority=4)
        return {"success": True, "mode": "job", "job_id": job_id}
    # 설치형(local): 백엔드가 직접 수집(브라우저 있음 → 리뷰+블로그 후기 모두)
    res = await collect_matjip_source(place_url, keyword)
    return {"success": True, "mode": "inline", "source_data": res.get("source_data", "")}


# ── AI 댓글 프롬프트 (고객이 직접 수정) ──────────────────────────────────
# /api/settings 아래에 두면 그 라우터가 관리자 전용이라 고객이 못 쓴다. 그래서 여기 둔다.
@router.get("/comment-prompt", summary="AI 댓글 프롬프트 조회")
async def get_comment_prompt(current_user: dict = Depends(get_current_user)):
    from mbam_nextgen.orchestrator import DEFAULT_CAFE_COMMENT_PROMPT
    from .settings import read_prompts, CAFE_COMMENT_PROMPT_KEY
    data = read_prompts() or {}
    return {
        "prompt": data.get(CAFE_COMMENT_PROMPT_KEY) or "",
        "default": DEFAULT_CAFE_COMMENT_PROMPT,
        "placeholders": {
            "{keyword}": "설정한 메인 키워드 (없으면 빈 값)",
            "{content}": "카페 게시글 본문 앞부분",
            "{tone}": "후보마다 다르게 배정되는 톤·화자·길이·반응 지점·타이핑 습관 + 이미 쓴 댓글 목록(같은 글/다른 글) — 계정끼리, 그리고 글끼리 댓글이 겹치지 않게 합니다. 지우면 댓글이 전부 비슷해집니다",
        },
    }


@router.post("/comment-prompt", summary="AI 댓글 프롬프트 저장")
async def update_comment_prompt(body: dict = Body(...), current_user: dict = Depends(get_current_user)):
    from .settings import read_prompts, write_prompts, CAFE_COMMENT_PROMPT_KEY
    data = read_prompts() or {}
    p = (body.get("prompt") or "").strip()
    if p:
        data[CAFE_COMMENT_PROMPT_KEY] = p          # 빈 값으로 저장하면 기본값으로 되돌린다
    else:
        data.pop(CAFE_COMMENT_PROMPT_KEY, None)
    write_prompts(data)
    return {"success": True,
            "message": "댓글 프롬프트를 저장했습니다." if p else "기본 프롬프트로 되돌렸습니다."}


# ── 원고 파일 업로드 → 제목·본문 파싱 ────────────────────────────────────
# AI 로 쓰지 않고 이미 써 둔 원고를 그대로 올려 발행하는 경로.
# .docx 는 python-docx 없이 표준 라이브러리로 푼다 — 동봉 런타임에 패키지를 추가하면
# 전체 재빌드(2.5GB)가 필요해지는데, docx 는 사실 zip 안의 XML 이라 그럴 이유가 없다.
_MANUSCRIPT_EXTS = (".txt", ".md", ".docx")


def _decode_text(raw: bytes) -> str:
    """한글 원고는 UTF-8 아니면 CP949 다. BOM 도 여기서 벗긴다."""
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _read_docx(raw: bytes) -> str:
    """.docx 의 word/document.xml 에서 문단 텍스트만 뽑는다."""
    import io
    import re as _re
    import zipfile
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        xml = z.read("word/document.xml").decode("utf-8", errors="replace")
    xml = _re.sub(r"<w:br[^>]*/>", "\n", xml)          # 줄바꿈
    xml = _re.sub(r"</w:p>", "\n", xml)                # 문단 끝
    xml = _re.sub(r"<[^>]+>", "", xml)                 # 나머지 태그 제거
    from xml.sax.saxutils import unescape
    return unescape(xml)


def _split_title_body(text: str):
    """원고에서 제목과 본문을 나눈다.

    '[제목] ...' 으로 시작하면 그걸 제목으로 쓰고 본문에서 뺀다.
    그 표시가 없으면 첫 번째 빈 줄이 아닌 줄을 제목으로 본다 — 원고 파일은 대개
    첫 줄이 제목이기 때문이다. 화면에서 제목·본문 둘 다 고칠 수 있으니
    잘못 잡혀도 사용자가 바로 바로잡을 수 있다.
    """
    import re as _re
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return "", ""
    m = _re.match(r"^\s*\[제목\]\s*(.+?)\s*(?:\n|$)", text)
    if m:
        return m.group(1).strip(), _re.sub(r"^\s*\[제목\].*?(?:\n|$)", "", text, count=1).strip()
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.strip():
            return ln.strip(), "\n".join(lines[i + 1:]).strip()
    return "", text


@router.post("/parse-manuscript", summary="원고 파일(txt/md/docx) → 제목·본문")
async def parse_manuscript(files: List[UploadFile] = File(...),
                           current_user: dict = Depends(get_current_user)):
    import os as _os
    import re as _re
    items, errors = [], []
    for f in files:
        name = f.filename or "원고"
        ext = _os.path.splitext(name)[1].lower()
        if ext not in _MANUSCRIPT_EXTS:
            errors.append({"filename": name, "error": f"지원하지 않는 형식입니다 ({ext or '확장자 없음'}). txt, md, docx 만 됩니다."})
            continue
        try:
            raw = await f.read()
            text = _read_docx(raw) if ext == ".docx" else _decode_text(raw)
            title, body = _split_title_body(text)
            if not body.strip():
                errors.append({"filename": name, "error": "본문이 비어 있습니다."})
                continue
            items.append({
                "filename": name,
                "title": title,
                "content": body,
                # 본문에 사진 자리가 몇 개 있는지 — 화면에서 '폴더 사진 N장 필요' 안내에 쓴다
                "image_markers": len(_re.findall(r"\[이미지(?::\s*\d+)?\]", body)),
            })
        except Exception as e:
            errors.append({"filename": name, "error": f"읽지 못했습니다: {e}"})
    if not items and errors:
        raise HTTPException(status_code=400, detail=errors[0]["error"])
    return {"items": items, "errors": errors}


# ── 카페 원고 프롬프트 (정보성 / 맛집) ────────────────────────────────────
# 기본 프롬프트를 통째로 바꾸면 출력 형식('제목: ...')이나 맛집의 '[이미지:N]' 마커 규칙이
# 깨져 발행이 실패한다. 그래서 여기 저장하는 값은 기본 규칙 뒤에 붙는 '추가 지시'다.
_POST_PROMPT_KEYS = {"cafe": "일키 포스팅 (일반 키워드)", "cafe_matjip": "맛집 포스팅"}


@router.get("/post-prompt", summary="카페 원고 추가 지시 조회")
async def get_post_prompt(current_user: dict = Depends(get_current_user)):
    from .settings import read_prompts
    data = read_prompts() or {}
    out = {}
    for key, label in _POST_PROMPT_KEYS.items():
        v = data.get(key)
        if isinstance(v, dict):                      # 블로그 프롬프트와 같은 구조로 저장된 경우
            v = v.get("claude_prompt") or v.get("gemini_prompt") or ""
        out[key] = {"label": label, "prompt": (v or "")}
    return {"items": out,
            "help": "여기 적은 내용이 기본 규칙 뒤에 '추가 지시'로 붙습니다. "
                    "말투·분량·금지어·마무리 문구 같은 것을 적어주세요."}


@router.post("/post-prompt", summary="카페 원고 추가 지시 저장")
async def update_post_prompt(body: dict = Body(...), current_user: dict = Depends(get_current_user)):
    from .settings import read_prompts, write_prompts
    key = (body.get("category") or "").strip()
    if key not in _POST_PROMPT_KEYS:
        raise HTTPException(status_code=400, detail="알 수 없는 분류입니다.")
    data = read_prompts() or {}
    p = (body.get("prompt") or "").strip()
    if p:
        data[key] = p
    else:
        data.pop(key, None)                          # 빈 값이면 추가 지시 없음(기본 동작)
    write_prompts(data)
    return {"success": True,
            "message": f"{_POST_PROMPT_KEYS[key]} 지시문을 저장했습니다." if p
                       else f"{_POST_PROMPT_KEYS[key]} 추가 지시를 비웠습니다."}


@router.post("/preview-comments", summary="AI 댓글 미리 생성 — 확인·수정 후 실행하기 위한 것")
async def preview_comments(req: CommentPreviewRequest,
                           current_user: dict = Depends(get_current_user)):
    """게시글 본문을 읽어 AI 댓글 후보를 만들어 돌려준다. 실제로 달지는 않는다.

    본문 추출은 SEO 분석기(비로그인 스크래핑)를 쓴다. 실행 때처럼 계정마다 브라우저를
    띄우지 않으므로 빠르고, 로그인 세션을 건드리지 않는다.
    프롬프트·후처리는 실행 경로와 같은 함수를 쓰므로 여기서 본 문장이 실제로 달릴 문장이다.
    """
    import asyncio
    from mbam_nextgen.orchestrator import (generate_cafe_comment, is_duplicate_comment,
                                           comment_seed)
    from mbam_nextgen.services.seo_analyzer import SeoAnalyzer
    from mbam_nextgen.services.soul import SoulRewriter

    urls = [u.strip() for u in (req.urls or []) if u and u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="게시글 URL을 입력하세요.")
    count = max(1, min(int(req.count or 3), 20))   # 보통 '선택한 계정 수'가 그대로 들어온다

    analyzer = SeoAnalyzer()
    try:
        details = await analyzer.analyze_multiple_urls(urls)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"본문을 가져오지 못했습니다: {e}")

    # 브라우저·세션 관리자가 딸린 WorkflowOrchestrator 를 통째로 만들 필요는 없다(AI 호출만 쓴다).
    soul = SoulRewriter()
    items, errors = [], []
    # 글을 가리지 않고 이번 미리보기에서 만든 모든 댓글. A글 댓글을 B글 생성 때 넘겨서
    # '소재만 바뀐 같은 문장 틀'이 글마다 되풀이되는 걸 막는다.
    made_all = []
    for u in urls:
        d = (details or {}).get(u) or {}
        if not d or "error" in d:
            errors.append({"url": u, "error": d.get("error", "본문을 가져올 수 없습니다.")})
            continue
        body = (d.get("full_text") or d.get("text_sample") or "").strip()
        if not body:
            errors.append({"url": u, "error": "본문이 비어 있습니다."})
            continue
        kw = (req.keyword or d.get("title") or "").strip()

        # 요청한 개수(=계정 수)만큼, 서로 '다른' 댓글을 만든다.
        # 후보마다 다른 '톤·화자·길이'를 주지 않으면 같은 프롬프트라 문장이 서로 비슷해진다.
        # seed 는 게시글마다 다르다 — 이게 없으면 모든 글이 똑같이 0,1,2… 번 조건으로
        # 시작해서 A글 1번 댓글과 B글 1번 댓글이 판박이가 된다(실제로 그랬다).
        seed = comment_seed(u)

        async def _one(idx: int, avoid: list):
            try:
                return await generate_cafe_comment(soul, kw, body, req.ai_provider,
                                                   variant=idx, avoid=avoid,
                                                   seed=seed, avoid_global=made_all)
            except Exception:
                return None

        comments = []
        attempt, max_attempts = 0, count * 3   # 중복이 나오면 더 뽑되, 무한정 돌지는 않게
        while len(comments) < count and attempt < max_attempts:
            need = count - len(comments)
            if not comments:
                # 첫 배치는 병렬로 빠르게. 서로를 못 보므로 겹칠 수 있는데, 그건 아래에서 거른다.
                batch = await asyncio.gather(*[_one(i, []) for i in range(need)])
            else:
                # 두 번째부터는 이미 만든 문장을 넘겨 '겹치지 않게' 뽑는다(그래서 순차).
                batch = [await _one(attempt + i, list(comments)) for i in range(need)]
            last_round = attempt + need >= max_attempts
            for c in batch:
                # 완전일치만 보면 '가보고 싶네요'/'가보고 싶어요' 가 둘 다 통과한다.
                if not c or len(comments) >= count:
                    continue
                if is_duplicate_comment(c, comments):
                    continue
                # 다른 글에 만든 댓글과도 겹치면 버린다 — 사용자가 본 문제가 바로 이것이다.
                # 단 마지막 판에서는 받아준다. 댓글이 아예 없는 것보다는 낫다.
                if not last_round and is_duplicate_comment(c, made_all):
                    continue
                comments.append(c)
            attempt += need
        if not comments:
            errors.append({"url": u, "error": "AI 댓글 생성에 실패했습니다. (설정에서 API 키를 확인하세요)"})
            continue
        made_all.extend(comments)
        items.append({"url": u, "title": d.get("title", ""), "used_keyword": kw,
                      "content_preview": body[:200], "comments": comments})

    return {"items": items, "errors": errors}


@router.post("/trigger-targeted", summary="다중 아이디로 타겟 게시글 댓글 작업 시작")
async def trigger_targeted(req: TargetPostRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    import asyncio
    user_id = get_user_id(current_user)

    accounts_data = []
    for acc_id in req.account_ids:
        acc = db.query(NaverAccount).filter(NaverAccount.id == acc_id, NaverAccount.user_id == user_id).first()
        if acc:
            # 비밀번호 복호화(암호화 저장 시). 에이전트로 payload 전달 시 평문이어야 로그인됨.
            pw = acc.naver_pw or ""
            try:
                from mbam_nextgen.backend.cipher_utils import decrypt_val
                if acc.naver_pw:
                    pw = decrypt_val(acc.naver_pw)
            except Exception:
                pw = acc.naver_pw or ""
            accounts_data.append({"id": acc.naver_id, "pw": pw})

    if not accounts_data:
        raise HTTPException(status_code=400, detail="선택된 계정이 없거나 권한이 없습니다.")

    # 계정별 프록시 배정 — 로컬 실행이든 에이전트 위임이든 배정은 서버가 한다
    # (프록시 목록이 DB 에 있으므로). 에이전트에는 배정 결과만 payload 로 넘긴다.
    proxy_map = build_proxy_map(db, user_id, accounts_data, req.use_proxy)

    task_id = str(uuid.uuid4())

    # 카페 댓글은 네이버 로그인·브라우저 자동화라 데이터센터 IP·무화면(클라우드)에선 불가.
    # 클라우드 모드에선 로컬 에이전트(집 IP·화면)에 위임하고, 에이전트가 task_status_store 로 로그를 중계한다.
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        task_status_store[task_id] = {"status": "running", "logs": [
            "[다중 타겟팅] 작업을 로컬 에이전트(집 PC)에 전달했습니다.",
            "에이전트가 실행을 시작하면 진행 로그가 여기에 표시됩니다. (에이전트가 켜져 있어야 합니다)",
        ]}
        payload = {
            "task_id": task_id,
            "accounts_data": accounts_data,
            "urls": req.urls,
            "keyword": req.keyword,
            "ai_provider": req.ai_provider,
            "delay_min": req.delay_min,
            "delay_max": req.delay_max,
            "account_delay_min": req.account_delay_min,
            "account_delay_max": req.account_delay_max,
            "use_tethering": req.use_tethering,
            "comment_content": req.comment_content,
            "do_like": req.do_like,
            "proxies": proxy_map,
            "comments_by_url": req.comments_by_url or {},
        }
        jobsvc.enqueue_job(db, user_id, "cafe_targeted_comment", payload, priority=5)
    else:
        task = asyncio.create_task(run_multi_target_task(task_id, req, accounts_data, proxy_map))
        auto_post_active_tasks[task_id] = task

    return {"success": True, "task_id": task_id, "message": "다중 계정 타겟 작업이 시작되었습니다.",
            "proxy_count": len(proxy_map)}

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
