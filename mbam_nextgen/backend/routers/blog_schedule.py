from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db, NaverAccount, BlogSchedule, BlogReservation
from ..auth import get_current_user

router = APIRouter(prefix="/api/blog-schedule", tags=["blog_schedule"])


def get_user_id(current_user: dict):
    return current_user.get("sub")  # Email or Login ID


class BlogScheduleCreate(BaseModel):
    account_id: Optional[str] = None                 # 단일 계정(레거시 호환)
    account_ids: Optional[list] = None               # 다중 계정 — 계정마다 예약 1건씩 생성
    schedule_time: str                      # "HH:MM"
    content_category: Optional[str] = None
    post_count_per_day: Optional[int] = 1
    ai_provider: Optional[str] = "claude"
    distribution_mode: Optional[str] = "normal"
    generate_card_news: Optional[bool] = True


@router.post("/schedules", summary="블로그 매일 자동발행 예약 추가 (다중 계정 지원)")
async def add_blog_schedule(
    req: BlogScheduleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id(current_user)
    # 단일/다중 계정 통합 — account_ids 우선, 없으면 account_id 하나
    acc_ids = [a for a in (req.account_ids or []) if a] or ([req.account_id] if req.account_id else [])
    if not acc_ids:
        raise HTTPException(status_code=400, detail="발행 계정을 1개 이상 선택하세요.")

    # 등록 시각이 예약 시각을 이미 지났으면 오늘은 건너뛰고 내일부터 (catch-up이 즉시 발행하지 않도록)
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo as _ZI
    _now_kst = _dt.now(_ZI("Asia/Seoul"))
    _passed_today = (req.schedule_time or "") <= _now_kst.strftime("%H:%M")
    _last_run = _now_kst.strftime("%Y-%m-%d") if _passed_today else None

    created = []
    for aid in acc_ids:
        # 소유권 검증: 본인 계정으로만 예약 가능 (IDOR 방지)
        acc = db.query(NaverAccount).filter(
            NaverAccount.id == aid, NaverAccount.user_id == user_id
        ).first()
        if not acc:
            continue  # 남의 계정/없는 계정은 건너뜀
        new_sch = BlogSchedule(
            user_id=user_id,
            account_id=aid,
            schedule_time=req.schedule_time,
            content_category=req.content_category,
            post_count_per_day=req.post_count_per_day or 1,
            ai_provider=req.ai_provider or "claude",
            distribution_mode=req.distribution_mode or "normal",
            generate_card_news=1 if req.generate_card_news else 0,
            last_run_date=_last_run,
        )
        db.add(new_sch)
        db.commit()
        db.refresh(new_sch)
        created.append(new_sch.id)
        # 로컬(설치형) 스케줄러에 즉시 등록 — 클라우드는 blog_daily_scheduler가 처리
        try:
            from mbam_nextgen.services.scheduler_service import scheduler_service
            scheduler_service.add_blog_schedule_job(new_sch.id, new_sch.schedule_time)
        except Exception as e:
            print(f"[blog_schedule] 스케줄러 즉시 등록 실패: {e}")

    if not created:
        raise HTTPException(status_code=404, detail="등록 가능한 계정을 찾을 수 없습니다.")
    return {"message": f"블로그 매일 발행 예약이 {len(created)}건 등록되었습니다.", "ids": created}


@router.get("/schedules", summary="블로그 매일 발행 예약 목록")
async def get_blog_schedules(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id(current_user)
    schedules = db.query(BlogSchedule).filter(BlogSchedule.user_id == user_id).all()

    result = []
    for s in schedules:
        acc = db.query(NaverAccount).filter(NaverAccount.id == s.account_id).first()
        if acc:
            result.append({
                "id": s.id,
                "account_id": s.account_id,
                "naver_id": acc.naver_id,
                "blog_addr": acc.blog_addr,
                "schedule_time": s.schedule_time,
                "content_category": s.content_category,
                "post_count_per_day": s.post_count_per_day,
                "ai_provider": s.ai_provider,
                "distribution_mode": s.distribution_mode,
                "generate_card_news": getattr(s, "generate_card_news", 1),
                "is_active": s.is_active,
                "last_run_date": s.last_run_date,
            })
    return result


@router.delete("/schedules/{schedule_id}", summary="블로그 매일 발행 예약 삭제")
async def delete_blog_schedule(
    schedule_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id(current_user)
    # 소유권 검증: 본인 예약만 삭제 (IDOR 방지)
    sch = db.query(BlogSchedule).filter(
        BlogSchedule.id == schedule_id, BlogSchedule.user_id == user_id
    ).first()
    if sch:
        db.delete(sch)
        db.commit()
        try:
            from mbam_nextgen.services.scheduler_service import scheduler_service
            scheduler_service.remove_blog_schedule_job(schedule_id)
        except Exception:
            pass
    return {"message": "예약이 삭제되었습니다."}


# ===================== 예약 포스팅 (1회) =====================
class BlogReservationCreate(BaseModel):
    account_id: str
    run_at: str                       # "YYYY-MM-DD HH:MM"
    keyword: str
    source_data: Optional[str] = None
    image_folder: Optional[str] = None
    ai_provider: Optional[str] = "claude"
    distribution_mode: Optional[str] = "normal"
    generate_card_news: Optional[bool] = True


@router.post("/reservations", summary="블로그 예약 포스팅 추가 (1회)")
async def add_reservation(req: BlogReservationCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    acc = db.query(NaverAccount).filter(NaverAccount.id == req.account_id, NaverAccount.user_id == user_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    if not (req.keyword or "").strip():
        raise HTTPException(status_code=400, detail="타겟 키워드를 입력하세요.")
    # run_at 형식 검증
    import datetime as _dt
    try:
        _dt.datetime.strptime(req.run_at, "%Y-%m-%d %H:%M")
    except Exception:
        raise HTTPException(status_code=400, detail="예약 일시 형식이 올바르지 않습니다. (YYYY-MM-DD HH:MM)")

    r = BlogReservation(
        user_id=user_id,
        account_id=req.account_id,
        run_at=req.run_at,
        keyword=req.keyword,
        source_data=req.source_data,
        image_folder=req.image_folder,
        ai_provider=req.ai_provider or "claude",
        distribution_mode=req.distribution_mode or "normal",
        generate_card_news=1 if req.generate_card_news else 0,
        status="pending",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    try:
        from mbam_nextgen.services.scheduler_service import scheduler_service
        scheduler_service.add_blog_reservation_job(r.id, r.run_at)
    except Exception as e:
        print(f"[blog_reservation] 스케줄러 등록 실패: {e}")
    return {"message": "예약 포스팅이 등록되었습니다.", "id": r.id}


@router.get("/reservations", summary="블로그 예약 포스팅 목록")
async def get_reservations(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    rows = db.query(BlogReservation).filter(BlogReservation.user_id == user_id).order_by(BlogReservation.run_at).all()
    result = []
    for r in rows:
        acc = db.query(NaverAccount).filter(NaverAccount.id == r.account_id).first()
        result.append({
            "id": r.id, "account_id": r.account_id, "naver_id": acc.naver_id if acc else "(삭제됨)",
            "run_at": r.run_at, "keyword": r.keyword,
            "has_source": bool(r.source_data), "has_image": bool(r.image_folder),
            "ai_provider": r.ai_provider, "distribution_mode": r.distribution_mode,
            "status": r.status, "result_url": r.result_url,
        })
    return result


@router.delete("/reservations/{reservation_id}", summary="블로그 예약 포스팅 삭제")
async def delete_reservation(reservation_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = get_user_id(current_user)
    r = db.query(BlogReservation).filter(BlogReservation.id == reservation_id, BlogReservation.user_id == user_id).first()
    if r:
        db.delete(r)
        db.commit()
        try:
            from mbam_nextgen.services.scheduler_service import scheduler_service
            scheduler_service.remove_blog_reservation_job(reservation_id)
        except Exception:
            pass
    return {"message": "예약이 삭제되었습니다."}
