"""티스토리 자동발행 라우터.

티스토리는 공식 API가 없어 브라우저 자동화(카카오 로그인→에디터)로만 발행 가능하고,
데이터센터 IP 차단 때문에 실제 실행은 로컬 에이전트(집 IP)가 담당한다.
- 계정 등록 후 1회 '기기 인증'(수동 카카오 로그인)을 에이전트 잡으로 실행해 영구 프로필을 만든다.
- 매일 자동발행 예약은 tistory_daily_scheduler(클라우드)가 잡을 적재하고 에이전트가 발행한다.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mbam_nextgen.backend.database import get_db, TistoryAccount, TistorySchedule
from mbam_nextgen.backend.auth import get_current_user
from mbam_nextgen.backend import jobs as jobsvc
from mbam_nextgen.backend.cipher_utils import encrypt_val

router = APIRouter(prefix="/api/tistory", tags=["Tistory Automation"])


def _uid(current_user: dict):
    return current_user.get("sub")


# ─────────────── 계정 ───────────────
class TistoryAccountCreate(BaseModel):
    kakao_id: str
    kakao_pw: Optional[str] = None
    blog_name: str   # xxx.tistory.com 의 xxx


@router.post("/accounts", summary="티스토리 계정 추가")
def add_account(req: TistoryAccountCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    pw = ""
    if req.kakao_pw:
        try:
            pw = encrypt_val(req.kakao_pw)
        except Exception:
            pw = req.kakao_pw
    acc = TistoryAccount(user_id=_uid(current_user), kakao_id=req.kakao_id, kakao_pw=pw,
                         blog_name=(req.blog_name or "").replace(".tistory.com", "").strip())
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return {"success": True, "id": acc.id}


@router.get("/accounts", summary="티스토리 계정 목록")
def list_accounts(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    rows = db.query(TistoryAccount).filter(TistoryAccount.user_id == _uid(current_user)).all()
    return {"success": True, "accounts": [
        {"id": a.id, "kakao_id": a.kakao_id, "blog_name": a.blog_name, "status": a.status} for a in rows
    ]}


@router.delete("/accounts/{account_id}", summary="티스토리 계정 삭제")
def delete_account(account_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    acc = db.query(TistoryAccount).filter(TistoryAccount.id == account_id, TistoryAccount.user_id == _uid(current_user)).first()
    if acc:
        db.delete(acc)
        db.commit()
    return {"success": True}


@router.post("/accounts/{account_id}/register", summary="티스토리 기기 인증(수동 카카오 로그인) — 에이전트 실행")
def register_account(account_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = _uid(current_user)
    acc = db.query(TistoryAccount).filter(TistoryAccount.id == account_id, TistoryAccount.user_id == user_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    # 로컬 에이전트가 브라우저를 열어 사용자가 카카오 로그인을 완료(집 PC 화면)
    jobsvc.enqueue_job(db, user_id, "tistory_register", {"account_id": acc.id}, priority=4)
    return {"success": True, "message": "PC 에이전트에서 로그인 창이 열립니다. 카카오 로그인을 완료해 주세요."}


# ─────────────── 예약 ───────────────
class TistoryScheduleCreate(BaseModel):
    account_ids: Optional[list] = None
    account_id: Optional[str] = None
    schedule_time: str
    content_category: Optional[str] = None
    post_count_per_day: Optional[int] = 1
    ai_provider: Optional[str] = "gemini"


@router.post("/schedules", summary="티스토리 매일 자동발행 예약 추가")
def add_schedule(req: TistoryScheduleCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = _uid(current_user)
    acc_ids = [a for a in (req.account_ids or []) if a] or ([req.account_id] if req.account_id else [])
    if not acc_ids:
        raise HTTPException(status_code=400, detail="발행할 티스토리 계정을 1개 이상 선택하세요.")
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _ZI
    _now = _dt.now(_ZI("Asia/Seoul"))
    _last = _now.strftime("%Y-%m-%d") if (req.schedule_time or "") <= _now.strftime("%H:%M") else None
    created = []
    for aid in acc_ids:
        acc = db.query(TistoryAccount).filter(TistoryAccount.id == aid, TistoryAccount.user_id == user_id).first()
        if not acc:
            continue
        sch = TistorySchedule(user_id=user_id, account_id=aid, schedule_time=req.schedule_time,
                              content_category=req.content_category, post_count_per_day=req.post_count_per_day or 1,
                              ai_provider=req.ai_provider or "gemini", last_run_date=_last)
        db.add(sch)
        db.commit()
        db.refresh(sch)
        created.append(sch.id)
    if not created:
        raise HTTPException(status_code=404, detail="등록 가능한 계정을 찾을 수 없습니다.")
    return {"message": f"티스토리 매일 발행 예약이 {len(created)}건 등록되었습니다.", "ids": created}


@router.get("/schedules", summary="티스토리 매일 발행 예약 목록")
def list_schedules(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    rows = db.query(TistorySchedule).filter(TistorySchedule.user_id == _uid(current_user)).all()
    out = []
    for s in rows:
        acc = db.query(TistoryAccount).filter(TistoryAccount.id == s.account_id).first()
        out.append({
            "id": s.id, "account_id": s.account_id,
            "naver_id": (acc.blog_name + ".tistory.com") if acc else "(삭제됨)",  # 프론트 공용 렌더 호환
            "schedule_time": s.schedule_time, "content_category": s.content_category,
            "post_count_per_day": s.post_count_per_day, "ai_provider": s.ai_provider,
            "generate_card_news": 0, "distribution_mode": "normal",
            "is_active": s.is_active, "last_run_date": s.last_run_date,
            "last_run_url": s.last_run_url, "last_run_title": s.last_run_title,
        })
    return out


@router.delete("/schedules/{schedule_id}", summary="티스토리 매일 발행 예약 삭제")
def delete_schedule(schedule_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    sch = db.query(TistorySchedule).filter(TistorySchedule.id == schedule_id, TistorySchedule.user_id == _uid(current_user)).first()
    if sch:
        db.delete(sch)
        db.commit()
    return {"message": "예약이 삭제되었습니다."}


@router.post("/schedules/{schedule_id}/toggle", summary="티스토리 매일 발행 예약 일시정지/재개")
def toggle_schedule(schedule_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    sch = db.query(TistorySchedule).filter(
        TistorySchedule.id == schedule_id, TistorySchedule.user_id == _uid(current_user)
    ).first()
    if not sch:
        raise HTTPException(status_code=404, detail="예약을 찾을 수 없습니다.")
    sch.is_active = 0 if sch.is_active else 1
    db.commit()
    return {"message": ("재개되었습니다." if sch.is_active else "일시정지되었습니다."),
            "is_active": sch.is_active}


# ─────────────── 발행 결과 영속화(persister) ───────────────
def _persist_tistory_post(db, user_id, payload, result):
    sid = (payload or {}).get("schedule_id")
    if not sid:
        return
    sch = db.query(TistorySchedule).filter(TistorySchedule.id == sid, TistorySchedule.user_id == user_id).first()
    if not sch:
        return
    if (result or {}).get("result_url"):
        sch.last_run_url = result["result_url"]
    if (result or {}).get("title"):
        sch.last_run_title = result["title"]


try:
    jobsvc.register_persister("tistory_post", _persist_tistory_post)
except Exception as _e:
    print(f"[tistory] persister 등록 실패: {_e}")
