import os
import re

filepath = r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\backend\routers\auth_router.py"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the imports and endpoints
replacement = """
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from ..auth import create_access_token, get_current_user, get_password_hash, verify_password
from ..database import get_db, Advertiser, Agency, Distributor
from datetime import timedelta
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login", summary="통합 로그인 (SSO)")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    admin_id = os.environ.get("SUPER_ADMIN_ID")
    admin_pw = os.environ.get("SUPER_ADMIN_PW")
    
    if admin_id and admin_pw and request.email == admin_id and request.password == admin_pw:
        access_token = create_access_token(
            data={"sub": admin_id, "role": "admin", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        return {"access_token": access_token, "token_type": "bearer"}

    # 1. Check Advertiser (email based)
    advertiser = db.query(Advertiser).filter(Advertiser.email == request.email).first()
    if advertiser and verify_password(request.password, advertiser.password):
        access_token = create_access_token(
            data={"sub": advertiser.email, "role": "advertiser", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        return {"access_token": access_token, "token_type": "bearer"}

    # 2. Check Agency (login_id based)
    agency = db.query(Agency).filter(Agency.login_id == request.email).first()
    if agency and verify_password(request.password, agency.password):
        access_token = create_access_token(
            data={"sub": agency.login_id, "role": "agency", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        return {"access_token": access_token, "token_type": "bearer"}

    # 3. Check Distributor (login_id based)
    distributor = db.query(Distributor).filter(Distributor.login_id == request.email).first()
    if distributor and verify_password(request.password, distributor.password):
        access_token = create_access_token(
            data={"sub": distributor.login_id, "role": "distributor", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        return {"access_token": access_token, "token_type": "bearer"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="아이디/이메일 또는 비밀번호가 올바르지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.get("/me", summary="현재 인증된 사용자 정보 조회")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "email": current_user.get("sub"),
        "role": current_user.get("role"),
        "provider": current_user.get("provider")
    }
"""

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(replacement.strip())

print("auth_router.py rewritten for SSO.")
