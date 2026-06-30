# -*- coding: utf-8 -*-
"""
플랜별 한도(계정 수 / 일일 작업 수) 해석 + 일일 사용량 집행.

한도 우선순위:  사용자 개별값(custom_limits) > 플랜값(plans.json) > 전역 기본값
모든 숫자는 관리자 페이지에서 plans.json / 사용자 쿼터로 변경 가능.
"""
import json
import os
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import Advertiser, DailyUsage

# 코드에 박지 않는다 — 어디까지나 plans.json/사용자값이 없을 때의 안전 기본
DEFAULT_LIMITS = {
    "max_naver_accounts": 5,
    "daily_limits": {
        "blog_post": 1,
        "cafe_post": 2,
        "cafe_comment": 10,
        "boost": 20,
        "place_news": 1,
    },
}

ACTION_TYPES = ("blog_post", "cafe_post", "cafe_comment", "boost", "place_news")


def _plans_path() -> str:
    return os.path.join(os.path.dirname(__file__), "config", "plans.json")


def load_plans() -> list:
    path = _plans_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _plan_for(plan_type: str) -> dict:
    """plan_type 으로 plans.json 항목 찾기 (id 또는 name, 대소문자 무시)."""
    if not plan_type:
        return {}
    pt = str(plan_type).strip().lower()
    for p in load_plans():
        if str(p.get("id", "")).lower() == pt or str(p.get("name", "")).lower() == pt:
            return p
    return {}


def get_user_limits(user: Advertiser) -> dict:
    """이 사용자에게 적용되는 최종 한도(계정수 + 작업별 일일한도)."""
    plan = _plan_for(getattr(user, "plan_type", None))

    max_accounts = plan.get("max_naver_accounts", DEFAULT_LIMITS["max_naver_accounts"])
    daily = dict(DEFAULT_LIMITS["daily_limits"])
    daily.update(plan.get("daily_limits") or {})

    # 사용자 개별 override
    raw = getattr(user, "custom_limits", None)
    if raw:
        try:
            ov = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if "max_naver_accounts" in ov and ov["max_naver_accounts"] is not None:
                max_accounts = ov["max_naver_accounts"]
            daily.update(ov.get("daily_limits") or {})
        except Exception:
            pass

    return {"max_naver_accounts": int(max_accounts), "daily_limits": daily}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_daily_count(db: Session, user_id: str, action_type: str,
                    naver_account_id: str = None, date_str: str = None) -> int:
    date_str = date_str or _today()
    q = db.query(func.coalesce(func.sum(DailyUsage.count), 0)).filter(
        DailyUsage.user_id == user_id,
        DailyUsage.action_type == action_type,
        DailyUsage.date_str == date_str,
    )
    if naver_account_id is not None:
        q = q.filter(DailyUsage.naver_account_id == naver_account_id)
    return int(q.scalar() or 0)


def check_daily_limit(db: Session, user: Advertiser, action_type: str,
                      naver_account_id: str = None):
    """한도 초과면 403. (소비는 하지 않음 — 실행 직전 검사용)"""
    if getattr(user, "plan_type", None) == "admin":
        return
    limits = get_user_limits(user)
    cap = limits["daily_limits"].get(action_type)
    if cap is None:   # 정의 안 된 작업은 제한 없음
        return
    used = get_daily_count(db, user.id, action_type, naver_account_id)
    if used >= cap:
        label = "계정" if naver_account_id else "전체"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"오늘 이 {label}의 '{action_type}' 일일 한도({cap}건)를 모두 사용했습니다. 내일 다시 가능합니다.",
        )


def consume_daily(db: Session, user_id: str, action_type: str,
                  naver_account_id: str = None, amount: int = 1):
    """일일 카운터 +amount (원자적 upsert)."""
    date_str = _today()
    row = db.query(DailyUsage).filter(
        DailyUsage.user_id == user_id,
        DailyUsage.action_type == action_type,
        DailyUsage.date_str == date_str,
        DailyUsage.naver_account_id == naver_account_id,
    ).first()
    if row:
        db.query(DailyUsage).filter(DailyUsage.id == row.id).update(
            {DailyUsage.count: func.coalesce(DailyUsage.count, 0) + amount},
            synchronize_session=False,
        )
    else:
        db.add(DailyUsage(user_id=user_id, action_type=action_type,
                          date_str=date_str, naver_account_id=naver_account_id,
                          count=amount))
    db.commit()


def enforce_and_consume(db: Session, user: Advertiser, action_type: str,
                        naver_account_id: str = None):
    """검사 통과 시 1건 소비. 자동화 실행 직전에 호출."""
    check_daily_limit(db, user, action_type, naver_account_id)
    consume_daily(db, user.id, action_type, naver_account_id)


def check_account_limit(db: Session, user: Advertiser, current_count: int):
    """네이버 계정 추가 직전 검사. 한도 도달이면 403."""
    if getattr(user, "plan_type", None) == "admin":
        return
    limits = get_user_limits(user)
    cap = limits["max_naver_accounts"]
    if current_count >= cap:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"등록 가능한 네이버 계정 수({cap}개)를 초과했습니다. 플랜을 업그레이드 해주세요.",
        )
