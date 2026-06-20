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
    # 지금은 Advertiser(광고주) 테이블을 기본 사용자로 취급합니다.
    users = db.query(Advertiser).order_by(Advertiser.created_at.desc()).all()
    
    result = []
    for u in users:
        device_count = db.query(DeviceSession).filter(DeviceSession.user_id == u.id).count()
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
            "device_count": device_count
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
        
    db.query(DeviceSession).filter(DeviceSession.user_id == user_id).delete()
    db.commit()
    return {"message": "해당 사용자의 기기 등록이 성공적으로 초기화되었습니다. 이제 새로운 PC에서 로그인할 수 있습니다."}

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
