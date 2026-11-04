# -*- coding: utf-8 -*-
"""웹 회원 정기결제 API (/api/billing) — 실제 처리는 services/billing.py."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mbam_nextgen.backend.auth import get_current_user
from mbam_nextgen.backend.database import Advertiser, get_db
from mbam_nextgen.services import billing

router = APIRouter()


def _advertiser(current_user: dict, db: Session) -> Advertiser:
    # 자동결제는 일반 회원(광고주)만 — 대행사·총판은 관리자가 플랜을 직접 지정한다
    if current_user.get("role") != "advertiser":
        raise HTTPException(status_code=400, detail="이 계정은 관리자가 요금제를 지정합니다. 관리자에게 문의하세요.")
    user = db.query(Advertiser).filter(Advertiser.email == current_user.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다.")
    return user


def _run(fn):
    try:
        return fn()
    except billing.BillingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/config", summary="결제창 설정(클라이언트 키·고객 키)")
def billing_config(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.get("role") != "advertiser" or not billing.enabled():
        return {"enabled": False}
    user = _advertiser(current_user, db)
    return {"enabled": True, "client_key": billing.client_key(), "customer_key": user.id,
            "email": user.email, "name": user.business_name or ""}


@router.get("/me", summary="내 구독·결제 내역")
def billing_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.get("role") != "advertiser":
        return {"subscription": None, "payments": []}
    return billing.summary(db, _advertiser(current_user, db))


class SubscribeRequest(BaseModel):
    auth_key: str
    customer_key: str
    plan_id: str


@router.post("/subscribe", summary="카드 등록 결과로 구독 시작(첫 달 결제) 또는 카드·요금제 변경")
async def billing_subscribe(req: SubscribeRequest, current_user: dict = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    user = _advertiser(current_user, db)
    try:
        return await billing.start_subscription(db, user, req.auth_key, req.customer_key, req.plan_id)
    except billing.BillingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cancel", summary="구독 해지 예약(남은 기간까지 사용)")
def billing_cancel(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _advertiser(current_user, db)
    return _run(lambda: billing.cancel_subscription(db, user))


@router.post("/resume", summary="해지 예약 취소")
def billing_resume(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = _advertiser(current_user, db)
    return _run(lambda: billing.resume_subscription(db, user))
