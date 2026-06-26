from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db, NaverAccount, BlogSchedule
from ..auth import get_current_user

router = APIRouter(prefix="/api/blog-schedule", tags=["blog_schedule"])


def get_user_id(current_user: dict):
    return current_user.get("sub")  # Email or Login ID


class BlogScheduleCreate(BaseModel):
    account_id: str
    schedule_time: str                      # "HH:MM"
    content_category: Optional[str] = None
    post_count_per_day: Optional[int] = 1
    ai_provider: Optional[str] = "claude"
    distribution_mode: Optional[str] = "normal"
    generate_card_news: Optional[bool] = True


@router.post("/schedules", summary="블로그 매일 자동발행 예약 추가")
async def add_blog_schedule(
    req: BlogScheduleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_user_id(current_user)
    # 소유권 검증: 본인 계정으로만 예약 가능 (IDOR 방지)
    acc = db.query(NaverAccount).filter(
        NaverAccount.id == req.account_id, NaverAccount.user_id == user_id
    ).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")

    new_sch = BlogSchedule(
        user_id=user_id,
        account_id=req.account_id,
        schedule_time=req.schedule_time,
        content_category=req.content_category,
        post_count_per_day=req.post_count_per_day or 1,
        ai_provider=req.ai_provider or "claude",
        distribution_mode=req.distribution_mode or "normal",
        generate_card_news=1 if req.generate_card_news else 0,
    )
    db.add(new_sch)
    db.commit()
    db.refresh(new_sch)

    # 실행 중인 스케줄러에 즉시 등록 (서버 재시작 없이 바로 예약 동작)
    try:
        from mbam_nextgen.services.scheduler_service import scheduler_service
        scheduler_service.add_blog_schedule_job(new_sch.id, new_sch.schedule_time)
    except Exception as e:
        print(f"[blog_schedule] 스케줄러 즉시 등록 실패: {e}")

    return {"message": "블로그 매일 발행 예약이 등록되었습니다.", "id": new_sch.id}


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
