# -*- coding: utf-8 -*-
"""웹 회원 정기결제 — 토스페이먼츠 자동결제(빌링) 연동.

흐름
  1) 결제 페이지에서 토스 카드 등록창(requestBillingAuth) → 성공 시 authKey 가 돌아온다
  2) start_subscription: authKey → billingKey 발급 → 첫 달 결제 → 플랜 적용
  3) charge_due (스케줄러, 10분마다): 결제일이 된 구독을 billingKey 로 자동 결제
     · 성공: 기간 1개월 연장 + 이번 달 사용 횟수 초기화
     · 실패: 하루 뒤 재시도, 3번 실패하면 플랜 해제(ended)
  4) 해지(canceled): 남은 기간까지 쓰고, 기간이 끝나면 플랜 해제

키는 환경변수로만 받는다 — TOSS_CLIENT_KEY(브라우저용), TOSS_SECRET_KEY(서버 전용).
둘 다 없으면 결제 기능은 꺼진 상태(enabled=False)로 동작한다.
"""
import base64
import logging
import os
import secrets
from calendar import monthrange
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from mbam_nextgen.backend.database import Advertiser, BillingPayment, BillingSubscription
from mbam_nextgen.backend.limits import load_plans

logger = logging.getLogger("Billing")

TOSS_API = "https://api.tosspayments.com/v1"
MAX_RETRIES = 3                       # 연속 결제 실패 허용 횟수 — 넘으면 플랜 해제
RETRY_AFTER = timedelta(days=1)
EXPIRED_PLAN = "expired"              # 유료 기간이 끝난 회원의 plan_type


class BillingError(Exception):
    """사용자에게 그대로 보여줄 수 있는 결제 오류."""


def client_key() -> str:
    return os.getenv("TOSS_CLIENT_KEY", "").strip()


def _secret_key() -> str:
    return os.getenv("TOSS_SECRET_KEY", "").strip()


def enabled() -> bool:
    return bool(client_key() and _secret_key())


def find_plan(plan_id: str) -> dict:
    pid = (plan_id or "").strip().lower()
    for p in load_plans():
        if str(p.get("id", "")).lower() == pid and int(p.get("price") or 0) > 0:
            return p
    raise BillingError("선택한 요금제를 찾을 수 없습니다.")


def add_month(dt: datetime) -> datetime:
    """한 달 뒤 같은 날(31일 → 다음 달 말일)."""
    y, m = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
    return dt.replace(year=y, month=m, day=min(dt.day, monthrange(y, m)[1]))


# ── 토스 API ────────────────────────────────────────────────────────────
async def _toss(path: str, body: dict, idempotency_key: str = "") -> dict:
    auth = base64.b64encode(f"{_secret_key()}:".encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(TOSS_API + path, json=body, headers=headers)
    data = r.json() if r.content else {}
    if r.status_code >= 400:
        raise BillingError(data.get("message") or f"결제사 오류 (HTTP {r.status_code})")
    return data


async def issue_billing_key(auth_key: str, customer_key: str) -> dict:
    return await _toss("/billing/authorizations/issue",
                       {"authKey": auth_key, "customerKey": customer_key})


def _order_id(sub: BillingSubscription) -> str:
    # 토스 규칙: 6~64자, 영문·숫자·-·_ — 시도마다 새 번호(중복 결제 방지는 claim 이 맡는다)
    return f"mbam_{sub.user_id[:8]}_{datetime.utcnow():%Y%m%d%H%M%S}_{secrets.token_hex(3)}"


async def _charge(db: Session, sub: BillingSubscription, user: Advertiser, plan: dict) -> bool:
    """billingKey 로 1개월치 결제. 결과는 BillingPayment 에 남긴다. 성공 여부만 돌려준다."""
    order_id = _order_id(sub)
    amount = int(plan["price"])
    rec = BillingPayment(user_id=sub.user_id, order_id=order_id, plan_id=plan["id"], amount=amount)
    try:
        res = await _toss(f"/billing/{sub.billing_key}", {
            "customerKey": sub.customer_key,
            "amount": amount,
            "orderId": order_id,
            "orderName": f"마케팅연구소 {plan.get('name', plan['id'])} 월 구독",
            "customerEmail": user.email,
            "customerName": user.business_name or user.email,
        }, idempotency_key=order_id)
        ok = res.get("status") == "DONE"
        rec.status = "DONE" if ok else "FAILED"
        rec.payment_key = res.get("paymentKey")
        rec.receipt_url = (res.get("receipt") or {}).get("url")
        if not ok:
            rec.message = f"결제 상태: {res.get('status')}"
    except BillingError as e:
        ok, rec.status, rec.message = False, "FAILED", str(e)[:300]
    except Exception as e:                    # 네트워크 등 — 다음 재시도로 넘긴다
        ok, rec.status, rec.message = False, "FAILED", f"결제 요청 실패: {e}"[:300]
    db.add(rec)
    sub.last_error = None if ok else rec.message
    return ok


# ── 플랜 적용/해제 ──────────────────────────────────────────────────────
def _apply_plan(user: Advertiser, plan: dict):
    user.plan_type = plan["id"]
    user.max_usage = int(plan.get("max_usage") or 0)
    user.usage_count = 0                      # 결제 주기마다 이번 달 사용 횟수 초기화
    user.trial_ends_at = None


def _end_plan(user: Advertiser):
    user.plan_type = EXPIRED_PLAN
    user.max_usage = 0


def _renew_period(sub: BillingSubscription):
    now = datetime.utcnow()
    base = sub.current_period_end if (sub.current_period_end and sub.current_period_end > now) else now
    sub.current_period_end = add_month(base)
    sub.next_billing_at = sub.current_period_end
    sub.status = "active"
    sub.fail_count = 0


# ── 회원 요청 ───────────────────────────────────────────────────────────
async def start_subscription(db: Session, user: Advertiser, auth_key: str,
                             customer_key: str, plan_id: str) -> dict:
    """카드 등록 결과(authKey)로 구독을 시작하거나, 이용 중이면 카드·다음 달 플랜을 바꾼다."""
    if not enabled():
        raise BillingError("결제 기능이 아직 설정되지 않았습니다. 관리자에게 문의하세요.")
    if customer_key != user.id:
        raise BillingError("결제 정보가 로그인한 회원과 다릅니다. 다시 시도해 주세요.")
    plan = find_plan(plan_id)

    issued = await issue_billing_key(auth_key, customer_key)
    card = issued.get("card") or {}
    sub = db.query(BillingSubscription).filter(BillingSubscription.user_id == user.id).first()
    if not sub:
        sub = BillingSubscription(user_id=user.id, email=user.email, customer_key=customer_key)
        db.add(sub)
    sub.billing_key = issued.get("billingKey")
    sub.card_company = issued.get("cardCompany") or card.get("issuerCode")
    sub.card_number = card.get("number")
    sub.plan_id, sub.amount = plan["id"], int(plan["price"])

    now = datetime.utcnow()
    in_period = sub.current_period_end and sub.current_period_end > now
    if in_period and sub.status in ("active", "canceled"):
        # 이미 낸 기간이 남아 있다 — 카드·플랜만 바꾸고 다음 결제일부터 적용(이중 결제 없음)
        sub.status = "active"
        db.commit()
        return {"charged": False,
                "message": f"카드·요금제를 변경했습니다. {sub.current_period_end:%Y-%m-%d} 결제분부터 적용됩니다."}

    if not await _charge(db, sub, user, plan):
        sub.status = "ended" if not in_period else sub.status
        db.commit()
        raise BillingError(f"결제에 실패했습니다: {sub.last_error}")
    _renew_period(sub)
    _apply_plan(user, plan)
    db.commit()
    return {"charged": True,
            "message": f"{plan.get('name')} 요금제 결제가 완료되었습니다. 다음 결제일: {sub.next_billing_at:%Y-%m-%d}"}


def cancel_subscription(db: Session, user: Advertiser) -> dict:
    sub = db.query(BillingSubscription).filter(BillingSubscription.user_id == user.id).first()
    if not sub or sub.status not in ("active", "past_due"):
        raise BillingError("해지할 구독이 없습니다.")
    sub.status = "canceled"
    sub.next_billing_at = None
    db.commit()
    return {"message": f"해지 예약되었습니다. {sub.current_period_end:%Y-%m-%d} 까지 이용할 수 있습니다."}


def resume_subscription(db: Session, user: Advertiser) -> dict:
    sub = db.query(BillingSubscription).filter(BillingSubscription.user_id == user.id).first()
    if not sub or sub.status != "canceled" or not sub.current_period_end \
            or sub.current_period_end <= datetime.utcnow():
        raise BillingError("다시 시작할 수 있는 구독이 없습니다. 요금제를 새로 선택해 주세요.")
    sub.status = "active"
    sub.next_billing_at = sub.current_period_end
    db.commit()
    return {"message": f"구독을 계속합니다. 다음 결제일: {sub.next_billing_at:%Y-%m-%d}"}


def summary(db: Session, user: Advertiser) -> dict:
    sub = db.query(BillingSubscription).filter(BillingSubscription.user_id == user.id).first()
    pays = (db.query(BillingPayment).filter(BillingPayment.user_id == user.id)
            .order_by(BillingPayment.created_at.desc()).limit(12).all())
    iso = lambda d: d.isoformat() if d else None
    return {
        "subscription": None if not sub else {
            "plan_id": sub.plan_id, "amount": sub.amount, "status": sub.status,
            "card_company": sub.card_company, "card_number": sub.card_number,
            "current_period_end": iso(sub.current_period_end),
            "next_billing_at": iso(sub.next_billing_at),
            "fail_count": sub.fail_count, "last_error": sub.last_error,
        },
        "payments": [{"order_id": p.order_id, "plan_id": p.plan_id, "amount": p.amount,
                      "status": p.status, "receipt_url": p.receipt_url, "message": p.message,
                      "created_at": iso(p.created_at)} for p in pays],
    }


# ── 스케줄러 ────────────────────────────────────────────────────────────
def _claim(db: Session, sub: BillingSubscription) -> bool:
    """결제 직전에 next_billing_at 을 1시간 뒤로 밀어 '내가 처리 중'을 표시한다.
    서버가 두 개 떠 있어도 같은 구독을 두 번 결제하지 않게 하는 조건부 UPDATE."""
    n = (db.query(BillingSubscription)
         .filter(BillingSubscription.id == sub.id,
                 BillingSubscription.next_billing_at == sub.next_billing_at)
         .update({BillingSubscription.next_billing_at: datetime.utcnow() + timedelta(hours=1)},
                 synchronize_session=False))
    db.commit()
    db.refresh(sub)
    return n == 1


async def charge_due(db: Session) -> dict:
    """결제일이 된 구독 결제 + 기간이 끝난 해지 구독 정리. 처리 건수를 돌려준다."""
    now = datetime.utcnow()
    stats = {"charged": 0, "failed": 0, "ended": 0}

    # 1) 해지 예약 → 기간 종료 시 플랜 해제
    for sub in db.query(BillingSubscription).filter(
            BillingSubscription.status == "canceled",
            BillingSubscription.current_period_end <= now).all():
        user = db.query(Advertiser).filter(Advertiser.id == sub.user_id).first()
        sub.status = "ended"
        if user:
            _end_plan(user)
        stats["ended"] += 1
    db.commit()

    # 2) 정기 결제
    due = db.query(BillingSubscription).filter(
        BillingSubscription.status.in_(("active", "past_due")),
        BillingSubscription.next_billing_at <= now,
        BillingSubscription.billing_key.isnot(None)).all()
    for sub in due:
        if not _claim(db, sub):
            continue
        user = db.query(Advertiser).filter(Advertiser.id == sub.user_id).first()
        if not user:
            sub.status = "ended"
            db.commit()
            continue
        try:
            plan = find_plan(sub.plan_id)
        except BillingError:
            sub.status, sub.last_error = "past_due", "요금제가 삭제되어 결제할 수 없습니다."
            sub.next_billing_at = now + RETRY_AFTER
            db.commit()
            continue
        if await _charge(db, sub, user, plan):
            _renew_period(sub)
            sub.amount = int(plan["price"])
            _apply_plan(user, plan)
            stats["charged"] += 1
        else:
            sub.fail_count = (sub.fail_count or 0) + 1
            if sub.fail_count >= MAX_RETRIES:
                sub.status = "ended"
                sub.next_billing_at = None
                sub.current_period_end = now      # 재가입 시 새 기간이 '지금'부터 시작되도록
                _end_plan(user)
                stats["ended"] += 1
            else:
                sub.status = "past_due"
                sub.next_billing_at = now + RETRY_AFTER
            stats["failed"] += 1
        db.commit()
    if any(stats.values()):
        logger.info(f"[Billing] 정기결제 처리: {stats}")
    return stats
