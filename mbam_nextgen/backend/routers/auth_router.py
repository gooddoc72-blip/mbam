from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
import uuid
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ..auth import create_access_token, get_current_user, get_password_hash, verify_password
from ..database import get_db, Advertiser, Agency, Distributor
from datetime import timedelta, datetime
from ..cipher_utils import get_decrypted_env
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")

class LoginRequest(BaseModel):
    email: str
    password: str
    hwid: str = None  # 하드웨어 고유 식별자 (없을 경우 웹 브라우저 임시 접속으로 간주)

def check_hwid_limit(db: Session, user_id: str, hwid: str):
    if not hwid:
        return
        
    from ..database import DeviceSession
    devices = db.query(DeviceSession).filter(DeviceSession.user_id == user_id).all()
    hwids = [d.hwid for d in devices]
    
    if hwid not in hwids:
        if len(hwids) >= 2:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="최대 허용 기기 수(2대)를 초과했습니다. 기존 기기에서 접속하거나 관리자에게 기기 초기화를 요청하세요."
            )
        else:
            try:
                new_device = DeviceSession(user_id=user_id, hwid=hwid)
                db.add(new_device)
                db.commit()
            except IntegrityError:
                db.rollback()
                # If race condition happens, the device was inserted by another thread, which is fine
    else:
        device = db.query(DeviceSession).filter(DeviceSession.user_id == user_id, DeviceSession.hwid == hwid).first()
        if device:
            try:
                device.last_login = datetime.utcnow()
                db.commit()
            except IntegrityError:
                db.rollback()

@router.post("/login", summary="통합 로그인 (SSO)")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    admin_id = os.environ.get("SUPER_ADMIN_ID")
    admin_pw = os.environ.get("SUPER_ADMIN_PW")
    
    import secrets
    if admin_id and admin_pw and secrets.compare_digest(request.email, admin_id) and secrets.compare_digest(request.password, admin_pw):
        access_token = create_access_token(
            data={"sub": admin_id, "role": "admin", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        resp = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
        resp.set_cookie(key="mbam_token", value=access_token, httponly=True, samesite="lax", max_age=7*24*3600)
        return resp

    # 1. Check Advertiser (email based)
    advertiser = db.query(Advertiser).filter(Advertiser.email == request.email).first()
    if advertiser and verify_password(request.password, advertiser.password):
        check_hwid_limit(db, advertiser.id, request.hwid)
        access_token = create_access_token(
            data={"sub": advertiser.email, "role": "advertiser", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        resp = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
        resp.set_cookie(key="mbam_token", value=access_token, httponly=True, samesite="lax", max_age=7*24*3600)
        return resp

    # 2. Check Agency (login_id based)
    agency = db.query(Agency).filter(Agency.login_id == request.email).first()
    if agency and verify_password(request.password, agency.password):
        check_hwid_limit(db, agency.id, request.hwid)
        access_token = create_access_token(
            data={"sub": agency.login_id, "role": "agency", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        resp = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
        resp.set_cookie(key="mbam_token", value=access_token, httponly=True, samesite="lax", max_age=7*24*3600)
        return resp

    # 3. Check Distributor (login_id based)
    distributor = db.query(Distributor).filter(Distributor.login_id == request.email).first()
    if distributor and verify_password(request.password, distributor.password):
        check_hwid_limit(db, distributor.id, request.hwid)
        access_token = create_access_token(
            data={"sub": distributor.login_id, "role": "distributor", "provider": "local"},
            expires_delta=timedelta(days=7)
        )
        resp = JSONResponse(content={"access_token": access_token, "token_type": "bearer"})
        resp.set_cookie(key="mbam_token", value=access_token, httponly=True, samesite="lax", max_age=7*24*3600)
        return resp

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="아이디/이메일 또는 비밀번호가 올바르지 않습니다.",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.get("/me", summary="현재 인증된 사용자 정보 조회")
async def read_users_me(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    email = current_user.get("sub")
    user_info = {
        "email": email,
        "role": current_user.get("role"),
        "provider": current_user.get("provider")
    }
    
    role = current_user.get("role")
    
    if role != "admin":
        user = None
        if role == "advertiser":
            user = db.query(Advertiser).filter(Advertiser.email == email).first()
        elif role == "agency":
            user = db.query(Agency).filter(Agency.login_id == email).first()
        elif role == "distributor":
            user = db.query(Distributor).filter(Distributor.login_id == email).first()
            
        if user:
            user_info["plan_type"] = getattr(user, "plan_type", "unlimited")
            user_info["usage_count"] = getattr(user, "usage_count", 0)
            user_info["max_usage"] = getattr(user, "max_usage", 999999)
            user_info["trial_ends_at"] = getattr(user, "trial_ends_at", None)
            
    return user_info


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password", summary="본인 비밀번호 변경 (관리자·회원 공용)")
async def change_password(req: ChangePasswordRequest,
                          current_user: dict = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="새 비밀번호는 8자 이상이어야 합니다.")
    if req.new_password == req.current_password:
        raise HTTPException(status_code=400, detail="현재 비밀번호와 다른 비밀번호를 입력하세요.")

    role = current_user.get("role")
    sub = current_user.get("sub")

    # 관리자: DB 계정이 아니라 SUPER_ADMIN_PW 환경변수 인증 → .env + 프로세스 환경 갱신.
    # Railway 등 클라우드는 재배포 시 대시보드 환경변수로 되돌아가므로 그쪽도 함께 바꿔야 영구 적용.
    if role == "admin":
        import secrets as _secrets
        admin_pw = os.environ.get("SUPER_ADMIN_PW") or ""
        if not _secrets.compare_digest(req.current_password, admin_pw):
            raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")
        os.environ["SUPER_ADMIN_PW"] = req.new_password
        try:
            from .settings import write_env
            write_env({"SUPER_ADMIN_PW": req.new_password})
        except Exception:
            pass
        return {"message": "관리자 비밀번호가 변경되었습니다. "
                           "(클라우드 배포 환경이라면 Railway 대시보드의 SUPER_ADMIN_PW 환경변수도 "
                           "같은 값으로 바꿔야 재배포 후에도 유지됩니다.)"}

    user = None
    if role == "advertiser":
        user = db.query(Advertiser).filter(Advertiser.email == sub).first()
    elif role == "agency":
        user = db.query(Agency).filter(Agency.login_id == sub).first()
    elif role == "distributor":
        user = db.query(Distributor).filter(Distributor.login_id == sub).first()
    if not user:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    if not user.password:
        raise HTTPException(status_code=400, detail="소셜 로그인 계정은 비밀번호 변경을 지원하지 않습니다.")
    if not verify_password(req.current_password, user.password):
        raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")

    user.password = get_password_hash(req.new_password)
    db.commit()
    return {"message": "비밀번호가 성공적으로 변경되었습니다."}


@router.get("/login/{provider}", summary="소셜 로그인 시작")
async def social_login(provider: str, request: Request):
    import secrets as _secrets
    # CSRF 방어용 1회성 state (고정 문자열 대신 랜덤 생성 후 쿠키에 저장 → 콜백에서 대조)
    state = _secrets.token_urlsafe(16)

    if provider == "kakao":
        client_id = os.environ.get("KAKAO_CLIENT_ID", "")
        redirect_uri = f"{BASE_URL}/api/auth/callback/kakao"
        url = f"https://kauth.kakao.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&state={state}"
    elif provider == "naver":
        client_id = os.environ.get("NAVER_CLIENT_ID", "")
        redirect_uri = f"{BASE_URL}/api/auth/callback/naver"
        url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}"
    elif provider == "google":
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        redirect_uri = f"{BASE_URL}/api/auth/callback/google"
        scope = "email profile"
        url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={scope}&state={state}"
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    resp = RedirectResponse(url)
    resp.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite="lax")
    return resp

@router.get("/callback/{provider}", summary="소셜 로그인 콜백")
async def social_callback(provider: str, request: Request, code: str, state: str = None, db: Session = Depends(get_db)):
    # CSRF 방어: 시작 시 발급한 state 쿠키와 콜백 state 파라미터 대조
    import secrets as _secrets
    cookie_state = request.cookies.get("oauth_state")
    if not cookie_state or not state or not _secrets.compare_digest(cookie_state, state):
        return RedirectResponse(f"{FRONTEND_URL}/login?error=invalid_state")

    email = None
    social_id = None

    async with httpx.AsyncClient() as client:
        if provider == "kakao":
            client_id = os.environ.get("KAKAO_CLIENT_ID", "")
            client_secret = get_decrypted_env("KAKAO_CLIENT_SECRET")
            redirect_uri = f"{BASE_URL}/api/auth/social/callback/kakao"
            
            data = {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code": code
            }
            if client_secret:
                data["client_secret"] = client_secret
                
            token_resp = await client.post("https://kauth.kakao.com/oauth/token", data=data, headers={"Content-type": "application/x-www-form-urlencoded;charset=utf-8"})
            
            if token_resp.status_code != 200:
                print("Kakao Token Error:", token_resp.text)
                return RedirectResponse(f"{FRONTEND_URL}/login?error=kakao_token_failed")
            
            access_token = token_resp.json().get("access_token")
            user_resp = await client.get("https://kapi.kakao.com/v2/user/me", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if user_resp.status_code != 200:
                return RedirectResponse(f"{FRONTEND_URL}/login?error=kakao_user_failed")
            
            try:
                user_data = user_resp.json()
            except Exception:
                return RedirectResponse(f"{FRONTEND_URL}/login?error=kakao_json_failed")
            social_id = str(user_data.get("id"))
            kakao_account = user_data.get("kakao_account", {})
            email = kakao_account.get("email")
            if not email:
                email = f"{social_id}@kakao.local"
                
        elif provider == "naver":
            client_id = os.environ.get("NAVER_CLIENT_ID", "")
            client_secret = get_decrypted_env("NAVER_CLIENT_SECRET")
            token_resp = await client.post("https://nid.naver.com/oauth2.0/token", data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "state": state or "mbam_state",
                "code": code
            })
            if token_resp.status_code != 200:
                return RedirectResponse(f"{FRONTEND_URL}/login?error=naver_token_failed")
                
            access_token = token_resp.json().get("access_token")
            user_resp = await client.get("https://openapi.naver.com/v1/nid/me", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if user_resp.status_code != 200:
                return RedirectResponse(f"{FRONTEND_URL}/login?error=naver_user_failed")
                
            try:
                user_data = user_resp.json().get("response", {})
            except Exception:
                return RedirectResponse(f"{FRONTEND_URL}/login?error=naver_json_failed")
            social_id = user_data.get("id")
            email = user_data.get("email")
            if not email:
                email = f"{social_id}@naver.local"
                
        elif provider == "google":
            client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
            client_secret = get_decrypted_env("GOOGLE_CLIENT_SECRET")
            redirect_uri = f"{BASE_URL}/api/auth/social/callback/google"
            token_resp = await client.post("https://oauth2.googleapis.com/token", data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code
            })
            if token_resp.status_code != 200:
                return RedirectResponse(f"{FRONTEND_URL}/login?error=google_token_failed")
                
            access_token = token_resp.json().get("access_token")
            user_resp = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={
                "Authorization": f"Bearer {access_token}"
            })
            if user_resp.status_code != 200:
                return RedirectResponse(f"{FRONTEND_URL}/login?error=google_user_failed")
                
            try:
                user_data = user_resp.json()
            except Exception:
                return RedirectResponse(f"{FRONTEND_URL}/login?error=google_json_failed")
            social_id = user_data.get("id")
            email = user_data.get("email")

    if not email or not social_id:
        return RedirectResponse(f"{FRONTEND_URL}/login?error=social_login_failed")

    # DB 연동
    user = db.query(Advertiser).filter(
        (Advertiser.email == email) | 
        ((Advertiser.social_provider == provider) & (Advertiser.social_id == social_id))
    ).first()

    if not user:
        import uuid
        user = Advertiser(
            id=str(uuid.uuid4()),
            email=email,
            social_provider=provider,
            social_id=str(social_id),
            business_name=f"{provider.capitalize()} 연동 회원",
            status="active"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    jwt_token = create_access_token(
        data={"sub": user.email, "role": "advertiser", "provider": provider},
        expires_delta=timedelta(days=7)
    )

    resp = RedirectResponse(f"{FRONTEND_URL}/login?token={jwt_token}")
    resp.delete_cookie("oauth_state")
    return resp

class SignupRequest(BaseModel):
    email: str
    password: str
    fingerprint: str = ""   # 브라우저 기기지문(중복 무료체험 방지)


# 어뷰징 방지 한도 (같은 IP 는 공유될 수 있어 넉넉히, 기기지문은 엄격히)
SIGNUP_IP_LIMIT = 5          # 같은 IP 에서 허용할 총 가입 수
SIGNUP_IP_WINDOW_DAYS = 30   # 최근 N일 기준


def _client_ip(req: Request) -> str:
    xff = req.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()   # 프록시(Vercel/Railway) 뒤의 실제 클라이언트
    return req.client.host if req.client else ""


@router.post("/signup", summary="자체 회원가입 (무료 체험 5일 제공)")
async def signup(payload: SignupRequest, http_request: Request, db: Session = Depends(get_db)):
    from ..database import SignupAudit

    email = (payload.email or "").strip().lower()
    fp = (payload.fingerprint or "").strip()
    ip = _client_ip(http_request)
    ua = http_request.headers.get("user-agent", "")[:300]

    # 1. 이메일 중복
    if db.query(Advertiser).filter(Advertiser.email == email).first():
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")
    if db.query(Agency).filter(Agency.login_id == email).first():
        raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")

    # 2. 기기지문 중복 → 같은 기기로 다른 이메일 재가입 차단 (핵심)
    if fp and db.query(SignupAudit).filter(SignupAudit.fingerprint == fp).first():
        raise HTTPException(
            status_code=403,
            detail="이미 이 기기에서 무료 체험에 가입한 이력이 있습니다. 정식 이용을 원하시면 문의해 주세요.",
        )

    # 3. 같은 IP 과다 가입 차단 (공유 IP 고려해 넉넉한 한도)
    if ip:
        since = datetime.utcnow() - timedelta(days=SIGNUP_IP_WINDOW_DAYS)
        ip_count = db.query(SignupAudit).filter(
            SignupAudit.ip == ip, SignupAudit.created_at >= since
        ).count()
        if ip_count >= SIGNUP_IP_LIMIT:
            raise HTTPException(
                status_code=403,
                detail="이 네트워크에서 가입 한도를 초과했습니다. 잠시 후 다시 시도하거나 문의해 주세요.",
            )

    # 4. 신규 사용자 생성 (기본 활성, 5일 체험, 10회 제한)
    import uuid
    new_user = Advertiser(
        id=str(uuid.uuid4()),
        email=email,
        password=get_password_hash(payload.password),
        social_provider="local",
        business_name="신규 가입자",
        status="active",
        plan_type="trial",
        trial_ends_at=datetime.utcnow() + timedelta(days=5),
        usage_count=0,
        max_usage=10
    )
    db.add(new_user)
    # 5. 가입 이력 기록 (다음 어뷰징 판단용)
    db.add(SignupAudit(email=email, fingerprint=fp or None, ip=ip or None, user_agent=ua))
    db.commit()
    db.refresh(new_user)

    return {"message": "회원가입이 완료되었습니다."}
