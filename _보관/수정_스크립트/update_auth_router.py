import os

auth_router_py = r'''
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from ..auth import create_access_token, get_current_user, get_password_hash, verify_password
from ..database import get_db, User
from datetime import timedelta
import os
from dotenv import load_dotenv
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config
from starlette.responses import RedirectResponse

load_dotenv()

router = APIRouter()

# OAuth 설정
config = Config('.env')
oauth = OAuth(config)

oauth.register(
    name='kakao',
    client_id=os.environ.get('KAKAO_CLIENT_ID', 'DUMMY_KAKAO_ID'),
    client_secret=os.environ.get('KAKAO_CLIENT_SECRET', 'DUMMY_KAKAO_SECRET'),
    server_metadata_url='https://kauth.kakao.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid profile_nickname account_email'},
)

oauth.register(
    name='naver',
    client_id=os.environ.get('NAVER_CLIENT_ID', 'DUMMY_NAVER_ID'),
    client_secret=os.environ.get('NAVER_CLIENT_SECRET', 'DUMMY_NAVER_SECRET'),
    authorize_url='https://nid.naver.com/oauth2.0/authorize',
    access_token_url='https://nid.naver.com/oauth2.0/token',
    userinfo_endpoint='https://openapi.naver.com/v1/nid/me',
    client_kwargs={'scope': 'name email'},
)

oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', 'DUMMY_GOOGLE_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', 'DUMMY_GOOGLE_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/signup", summary="이메일 회원가입")
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == request.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")
    
    hashed_password = get_password_hash(request.password)
    new_user = User(
        email=request.email,
        hashed_password=hashed_password,
        provider="local"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "회원가입이 완료되었습니다.", "user_id": new_user.id}

@router.post("/login", summary="이메일 로그인")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email, User.provider == "local").first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "role": user.role, "provider": "local"},
        expires_delta=timedelta(days=7)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/login/{provider}", summary="소셜 로그인 리다이렉트")
async def login_social(provider: str, request: Request):
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=404, detail="지원하지 않는 소셜 로그인입니다.")
    redirect_uri = request.url_for('auth_callback', provider=provider)
    return await client.authorize_redirect(request, redirect_uri)

@router.get("/callback/{provider}", summary="소셜 로그인 콜백")
async def auth_callback(provider: str, request: Request, db: Session = Depends(get_db)):
    client = oauth.create_client(provider)
    if not client:
        raise HTTPException(status_code=404, detail="지원하지 않는 소셜 로그인입니다.")
    
    try:
        token = await client.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"인증 실패: {e}")
    
    user_info = None
    if provider == 'kakao':
        user_info = token.get('userinfo')
        email = user_info.get('email')
        social_id = str(user_info.get('sub'))
    elif provider == 'naver':
        resp = await client.get('https://openapi.naver.com/v1/nid/me', token=token)
        profile = resp.json().get('response', {})
        email = profile.get('email')
        social_id = profile.get('id')
    elif provider == 'google':
        user_info = token.get('userinfo')
        email = user_info.get('email')
        social_id = user_info.get('sub')
        
    if not social_id:
        raise HTTPException(status_code=400, detail="소셜 정보를 가져오지 못했습니다.")
        
    db_user = db.query(User).filter(User.social_id == social_id, User.provider == provider).first()
    if not db_user:
        # 이메일 충돌 확인
        if email:
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                # 같은 이메일이 있으면 그냥 연동해주거나 에러 발생
                db_user = existing
        
        if not db_user:
            db_user = User(
                email=email,
                provider=provider,
                social_id=social_id
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            
    access_token = create_access_token(
        data={"sub": db_user.email or db_user.social_id, "role": db_user.role, "provider": provider},
        expires_delta=timedelta(days=7)
    )
    
    # 프론트엔드로 리다이렉트 하면서 토큰 전달 (실제 운영에서는 쿠키를 사용하거나 URL 파라미터로 전달)
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(f"{frontend_url}/login/callback?token={access_token}")

@router.get("/me", summary="현재 인증된 사용자 정보 조회")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "email": current_user.get("sub"),
        "role": current_user.get("role"),
        "provider": current_user.get("provider")
    }
'''

with open(r"C:\Users\blocklabs02\Desktop\review_platform\마케팅 프로그램\mbam_nextgen\backend\routers\auth_router.py", "w", encoding="utf-8") as f:
    f.write(auth_router_py.strip())

print("auth_router.py updated.")
