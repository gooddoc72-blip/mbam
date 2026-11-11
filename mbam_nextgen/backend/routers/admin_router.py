from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from datetime import datetime
import json
import os

from ..database import get_db, Advertiser, Agency, Distributor
from ..auth import get_current_user, verify_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])

class QuotaUpdateRequest(BaseModel):
    plan_type: str
    max_usage: int
    trial_ends_at: Optional[datetime] = None

@router.get("/users", summary="전체 사용자 목록 조회")
async def get_all_users(db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    from ..database import DeviceSession
    from ..models import UserAIKey
    from .auth_router import WEB_HWID_PREFIX
    # 지금은 Advertiser(광고주) 테이블을 기본 사용자로 취급합니다.
    users = db.query(Advertiser).order_by(Advertiser.created_at.desc()).all()

    # BYOK(자기 AI키 보유) 사용자 집합 — user_id 는 로그인 sub(=email)
    byok = set()
    try:
        for r in db.query(UserAIKey).all():
            if r.claude_key or r.gemini_key or r.openai_key:
                byok.add(r.user_id)
    except Exception:
        pass

    result = []
    for u in users:
        device_count = (db.query(DeviceSession)
                        .filter(DeviceSession.user_id == u.id,
                                ~DeviceSession.hwid.like(WEB_HWID_PREFIX + "%"))
                        .count())  # PC(에이전트) 만 — 브라우저 기록은 제외
        result.append({
            "id": u.id,
            "email": u.email,
            "business_name": u.business_name,
            "status": u.status,
            "plan_type": u.plan_type,
            "usage_count": u.usage_count,
            "max_usage": u.max_usage,
            "trial_ends_at": u.trial_ends_at,
            "created_at": u.created_at,
            "device_count": device_count,
            "has_byok": u.email in byok,  # True=설치형(본인키), False=웹(서버키+쿼터)
        })
    return result

@router.put("/users/{user_id}/quota", summary="사용자 플랜 및 쿼터 수정")
async def update_user_quota(user_id: str, req: QuotaUpdateRequest, db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    user = db.query(Advertiser).filter(Advertiser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
    user.plan_type = req.plan_type
    user.max_usage = req.max_usage
    if req.trial_ends_at:
        user.trial_ends_at = req.trial_ends_at
        
    db.commit()
    return {"message": "쿼터가 성공적으로 수정되었습니다."}

@router.post("/users/{user_id}/reset-devices", summary="사용자 기기(HWID) 등록 초기화")
async def reset_user_devices(user_id: str, db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    from ..database import DeviceSession
    user = db.query(Advertiser).filter(Advertiser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
    from ..database import DeviceRequest
    db.query(DeviceSession).filter(DeviceSession.user_id == user_id).delete()
    db.query(DeviceRequest).filter(DeviceRequest.user_id == user_id).delete()  # 거절 기록도 초기화
    db.commit()
    return {"message": "PC 등록이 초기화되었습니다. 새 PC 에서 에이전트로 로그인하면 승인 요청이 들어옵니다."}


# ── PC 승인 (고객당 PC 2대, 모든 PC 관리자 승인) ─────────────────────────────

def _approved_pcs(db: Session, user_id: str):
    from ..database import DeviceSession
    from .auth_router import WEB_HWID_PREFIX
    return (db.query(DeviceSession)
            .filter(DeviceSession.user_id == user_id, ~DeviceSession.hwid.like(WEB_HWID_PREFIX + "%"))
            .order_by(DeviceSession.last_login.desc()).all())


def _pc_dict(d):
    return {"id": d.id, "pc_name": d.pc_name, "hwid": (d.hwid or "")[-6:],
            "last_login": d.last_login}


@router.get("/device-requests", summary="PC 승인 대기 목록")
async def list_device_requests(db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    from ..database import DeviceRequest
    rows = (db.query(DeviceRequest).filter(DeviceRequest.status == "pending")
            .order_by(DeviceRequest.requested_at.asc()).all())
    out = []
    for r in rows:
        out.append({
            "id": r.id, "user_id": r.user_id, "user_email": r.user_email,
            "pc_name": r.pc_name, "hwid": (r.hwid or "")[-6:], "requested_at": r.requested_at,
            "approved": [_pc_dict(d) for d in _approved_pcs(db, r.user_id)],
        })
    return out


class ApproveDeviceRequest(BaseModel):
    replace_device_id: Optional[str] = None  # 이미 2대면 해제할 기존 PC


@router.post("/device-requests/{req_id}/approve", summary="PC 승인")
async def approve_device_request(req_id: str, body: ApproveDeviceRequest = None,
                                 db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    from ..database import DeviceSession, DeviceRequest
    from .auth_router import MAX_PC_DEVICES
    r = db.query(DeviceRequest).filter(DeviceRequest.id == req_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다.")
    approved = _approved_pcs(db, r.user_id)
    replace_id = body.replace_device_id if body else None
    if replace_id:
        target = next((d for d in approved if d.id == replace_id), None)
        if not target:
            raise HTTPException(status_code=400, detail="해제할 PC 를 찾을 수 없습니다.")
        db.delete(target)
        approved = [d for d in approved if d.id != replace_id]
    if len(approved) >= MAX_PC_DEVICES:
        raise HTTPException(status_code=409,
                            detail=f"이미 PC {MAX_PC_DEVICES}대가 승인되어 있습니다. 해제할 PC 를 선택하세요.")
    exists = (db.query(DeviceSession)
              .filter(DeviceSession.user_id == r.user_id, DeviceSession.hwid == r.hwid).first())
    if not exists:
        db.add(DeviceSession(user_id=r.user_id, hwid=r.hwid, pc_name=r.pc_name))
    db.delete(r)
    db.commit()
    return {"message": f"{r.user_email or ''} 의 PC({r.pc_name or '-'}) 를 승인했습니다. 에이전트가 곧 자동으로 시작됩니다."}


@router.post("/device-requests/{req_id}/reject", summary="PC 승인 거절")
async def reject_device_request(req_id: str, db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    from ..database import DeviceRequest
    r = db.query(DeviceRequest).filter(DeviceRequest.id == req_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다.")
    r.status = "rejected"
    r.decided_at = datetime.utcnow()
    db.commit()
    return {"message": "거절했습니다. 이 PC 는 'PC 등록 초기화' 전까지 다시 요청할 수 없습니다."}


@router.get("/users/{user_id}/devices", summary="회원의 승인된 PC 목록")
async def list_user_devices(user_id: str, db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    return [_pc_dict(d) for d in _approved_pcs(db, user_id)]


@router.delete("/users/{user_id}/devices/{device_id}", summary="승인된 PC 1대 해제")
async def remove_user_device(user_id: str, device_id: str,
                             db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    from ..database import DeviceSession
    d = (db.query(DeviceSession)
         .filter(DeviceSession.user_id == user_id, DeviceSession.id == device_id).first())
    if not d:
        raise HTTPException(status_code=404, detail="PC 를 찾을 수 없습니다.")
    db.delete(d)
    db.commit()
    return {"message": "PC 승인을 해제했습니다. 그 PC 의 에이전트는 1분 안에 멈춥니다."}

class PasswordResetRequest(BaseModel):
    new_password: str

@router.put("/users/{user_id}/password", summary="사용자 비밀번호 재설정 (관리자)")
async def reset_user_password(user_id: str, req: PasswordResetRequest,
                              db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    from ..auth import get_password_hash
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="새 비밀번호는 8자 이상이어야 합니다.")
    user = db.query(Advertiser).filter(Advertiser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    user.password = get_password_hash(req.new_password)
    db.commit()
    return {"message": f"{user.email} 회원의 비밀번호가 재설정되었습니다."}

@router.delete("/users/{user_id}", summary="사용자 삭제")
async def delete_user(user_id: str, db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    user = db.query(Advertiser).filter(Advertiser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        
    db.delete(user)
    db.commit()
    return {"message": "사용자가 삭제되었습니다."}

def get_plans_config_path():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "plans.json")

@router.get("/plans", summary="요금제 정보 조회 (공개)")
async def get_plans():
    config_path = get_plans_config_path()
    if not os.path.exists(config_path):
        return []
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)

@router.put("/plans", summary="요금제 정보 수정 (관리자)")
async def update_plans(plans: List[Dict[str, Any]], admin: dict = Depends(verify_admin)):
    config_path = get_plans_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(plans, f, ensure_ascii=False, indent=2)
    return {"message": "요금제 설정이 성공적으로 저장되었습니다."}


# ── 사용자별 한도(계정수/일일한도) 개별 지정 + 오늘 사용량 조회 ──────────────
class LimitsOverrideRequest(BaseModel):
    # null 이면 해당 항목은 플랜 기본값을 따름
    max_naver_accounts: Optional[int] = None
    daily_limits: Optional[Dict[str, int]] = None


@router.get("/users/{user_id}/limits", summary="사용자 적용 한도 + 오늘 사용량 조회")
async def get_user_limits_view(user_id: str, db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    from ..limits import get_user_limits, get_daily_count, ACTION_TYPES
    user = db.query(Advertiser).filter(Advertiser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    effective = get_user_limits(user)
    today_usage = {a: get_daily_count(db, user.id, a) for a in ACTION_TYPES}
    override = None
    if getattr(user, "custom_limits", None):
        try:
            override = json.loads(user.custom_limits)
        except Exception:
            override = None
    return {"plan_type": user.plan_type, "effective": effective,
            "override": override, "today_usage": today_usage}


@router.put("/users/{user_id}/limits", summary="사용자 한도 개별 지정(override)")
async def set_user_limits(user_id: str, req: LimitsOverrideRequest,
                          db: Session = Depends(get_db), admin: dict = Depends(verify_admin)):
    user = db.query(Advertiser).filter(Advertiser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    payload = {k: v for k, v in req.dict().items() if v is not None}
    user.custom_limits = json.dumps(payload, ensure_ascii=False) if payload else None
    db.commit()
    return {"message": "사용자 한도가 저장되었습니다.", "override": payload or None}
