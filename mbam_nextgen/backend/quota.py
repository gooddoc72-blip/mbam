from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from .database import get_db, Advertiser, Agency, Distributor
from .auth import get_current_user

def check_quota(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    API 접근 시 사용자의 쿼터를 검사하는 의존성 함수.
    쿼터(max_usage)를 초과했거나 만료일(trial_ends_at)이 지났으면 403 에러 반환.
    """
    user_email = current_user.get("sub")
    
    role = current_user.get("role")
    
    # 1. 최고관리자는 예외 (무제한)
    if role == "admin":
        return current_user
        
    user = None
    if role == "advertiser":
        user = db.query(Advertiser).filter(Advertiser.email == user_email).first()
    elif role == "agency":
        user = db.query(Agency).filter(Agency.login_id == user_email).first()
    elif role == "distributor":
        user = db.query(Distributor).filter(Distributor.login_id == user_email).first()
        
    if not user:
        raise HTTPException(status_code=401, detail="사용자 정보를 찾을 수 없습니다.")
        
    # 2. 횟수 제한 체크
    if user.usage_count >= user.max_usage:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"사용 가능한 횟수({user.max_usage}회)를 모두 소진하였습니다. 플랜을 업그레이드 해주세요."
        )
        
    # 3. 무료체험 기한 체크 (trial 플랜인 경우)
    if user.plan_type == "trial" and user.trial_ends_at:
        if datetime.utcnow() > user.trial_ends_at:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="무료 체험 기간(5일)이 만료되었습니다. 유료 플랜으로 전환해 주세요."
            )
            
    # 통과 시 user_id 혹은 user 객체를 넘겨주기 위해 dict에 담아 리턴
    current_user["usage_count"] = user.usage_count
    current_user["max_usage"] = user.max_usage
    current_user["db_user_id"] = user.id
    return current_user

def increment_quota(user_email: str, role: str, db: Session):
    """
    작업 성공 시 사용 횟수를 1 증가시킵니다.
    """
    user = None
    if role == "advertiser":
        user = db.query(Advertiser).filter(Advertiser.email == user_email).first()
    elif role == "agency":
        user = db.query(Agency).filter(Agency.login_id == user_email).first()
    elif role == "distributor":
        user = db.query(Distributor).filter(Distributor.login_id == user_email).first()
        
    if user:
        user.usage_count += 1
        db.commit()
