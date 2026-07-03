# -*- coding: utf-8 -*-
"""
MBAM 라이선스(인증코드) 서버
================================
- 인증코드(license code) 1개당 PC 1대(HWID)에 묶입니다.
- 최초 실행 시 /activate 로 코드+HWID 를 바인딩하고, 이후 /verify 로 검증합니다.
- 관리자 토큰(ADMIN_TOKEN)으로 코드 발급/조회/차단/PC 이전(reset) 을 합니다.

실행:
    set ADMIN_TOKEN=원하는_관리자_비밀  (없으면 자동 생성되어 콘솔에 출력)
    uvicorn server:app --host 0.0.0.0 --port 8005
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import string
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Integer
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ──────────────────────────────────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("LICENSE_DB_URL", "sqlite:///./license.db")

# 관리자 토큰: 환경변수로 주거나, 없으면 1회 생성해 콘솔에 출력 (재시작 시 유지하려면 .env 권장)
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")
if not ADMIN_TOKEN:
    ADMIN_TOKEN = secrets.token_urlsafe(24)
    print("=" * 60)
    print("[MBAM 라이선스 서버] ADMIN_TOKEN 이 환경변수에 없어 새로 생성했습니다:")
    print(f"  ADMIN_TOKEN = {ADMIN_TOKEN}")
    print("  (재시작 시 동일 값을 쓰려면 환경변수 ADMIN_TOKEN 에 넣어두세요)")
    print("=" * 60)

# 토큰 서명용 비밀키 (로그인 토큰 위조 방지). 없으면 ADMIN_TOKEN 기반으로 파생.
AUTH_SECRET = os.environ.get("AUTH_SECRET") or hashlib.sha256(("authsalt::" + ADMIN_TOKEN).encode()).hexdigest()

# 회원가입 시 무료 체험 기간(일)
TRIAL_DAYS = int(os.environ.get("TRIAL_DAYS", "5"))

# 서비스(브랜드) 이름
BRAND = os.environ.get("BRAND", "마케팅 연구소")

# 로그인 성공 후 이동할 사이트 주소.
#  - 기본은 같은 서버의 /app 페이지(데모용)
#  - 실제 분석 웹이 따로 있으면 APP_URL=https://app.내도메인 같은 식으로 교체
APP_URL = os.environ.get("APP_URL", "/app")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class License(Base):
    __tablename__ = "licenses"
    code = Column(String, primary_key=True, index=True)      # 인증코드
    hwid = Column(String, nullable=True, index=True)         # 묶인 PC (활성화 전 None)
    machine_name = Column(String, nullable=True)             # 사용자 PC 이름 메모
    memo = Column(String, nullable=True)                     # 고객명/부서 등
    is_active = Column(Boolean, default=True)                # 관리자 차단 여부
    max_activations = Column(Integer, default=1)             # PC 대수 (기본 1)
    expires_at = Column(DateTime, nullable=True)             # 만료일(구독). None=무기한
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)

class Device(Base):
    __tablename__ = "devices"
    hwid = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    status = Column(String, default="pending") # pending, approved, blocked
    created_at = Column(DateTime, default=datetime.utcnow)



class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # plan: 'trial'(체험) | 'paid'(유료) | 'blocked'(차단)
    plan = Column(String, default="trial")
    trial_expires_at = Column(DateTime, nullable=True)   # 체험 만료
    paid_expires_at = Column(DateTime, nullable=True)    # 유료 만료(None=무기한)
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)


Base.metadata.create_all(bind=engine)

app = FastAPI(title="MBAM License Server")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(x_admin_token: str = Header(None)):
    if not x_admin_token or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="관리자 인증 실패")
    return True


def _is_expired(lic: License) -> bool:
    return bool(lic.expires_at and lic.expires_at < datetime.utcnow())


def _public(lic: License) -> dict:
    return {
        "code": lic.code,
        "hwid": lic.hwid,
        "machine_name": lic.machine_name,
        "memo": lic.memo,
        "is_active": lic.is_active,
        "max_activations": lic.max_activations,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "created_at": lic.created_at.isoformat() if lic.created_at else None,
        "activated_at": lic.activated_at.isoformat() if lic.activated_at else None,
        "last_seen": lic.last_seen.isoformat() if lic.last_seen else None,
    }


# ──────────────────────────────────────────────────────────────────────────
# 클라이언트 엔드포인트
# ──────────────────────────────────────────────────────────────────────────
class ActivateRequest(BaseModel):
    code: str
    hwid: str
    machine_name: str = ""


class VerifyRequest(BaseModel):
    code: str
    hwid: str

class DeviceVerify(BaseModel):
    hwid: str

class ApprovalRequest(BaseModel):
    hwid: str
    name: str

@app.post("/activate")
def activate(req: ActivateRequest, db: Session = Depends(get_db)):
    """최초 인증: 코드를 이 PC(HWID)에 묶습니다."""
    code = (req.code or "").strip().upper().replace(" ", "")
    lic = db.query(License).filter(License.code == code).first()
    if not lic:
        raise HTTPException(status_code=404, detail="존재하지 않는 인증코드입니다.")
    if not lic.is_active:
        raise HTTPException(status_code=403, detail="차단된 인증코드입니다. 관리자에게 문의하세요.")
    if _is_expired(lic):
        raise HTTPException(status_code=403, detail="만료된 인증코드입니다.")

    now = datetime.utcnow()
    if not lic.hwid:
        # 최초 활성화 → 이 PC 에 바인딩
        lic.hwid = req.hwid
        lic.machine_name = req.machine_name[:120]
        lic.activated_at = now
        lic.last_seen = now
        db.commit()
        return {"authorized": True, "message": "인증이 완료되었습니다.",
                "expires_at": lic.expires_at.isoformat() if lic.expires_at else None}

    if lic.hwid == req.hwid:
        # 같은 PC 재활성화
        lic.last_seen = now
        db.commit()
        return {"authorized": True, "message": "이미 이 PC 에 인증된 코드입니다.",
                "expires_at": lic.expires_at.isoformat() if lic.expires_at else None}

    # 다른 PC 에 이미 묶임
    raise HTTPException(
        status_code=409,
        detail="이미 다른 PC 에 등록된 인증코드입니다. PC 를 변경하려면 관리자에게 이전을 요청하세요.",
    )


@app.post("/verify_license")
def verify_license(req: VerifyRequest, db: Session = Depends(get_db)):
    """실행 시마다 검증: 코드가 살아있고 이 PC 에 묶여 있는지 확인."""
    code = (req.code or "").strip().upper().replace(" ", "")
    lic = db.query(License).filter(License.code == code).first()
    if not lic:
        return {"authorized": False, "message": "존재하지 않는 인증코드입니다."}
    if not lic.is_active:
        return {"authorized": False, "message": "차단된 인증코드입니다."}
    if _is_expired(lic):
        return {"authorized": False, "message": "만료된 인증코드입니다."}
    if lic.hwid != req.hwid:
        if lic.hwid is None:
            return {"authorized": False, "message": "아직 활성화되지 않은 코드입니다."}
        return {"authorized": False, "message": "다른 PC 에 등록된 인증코드입니다."}

    lic.last_seen = datetime.utcnow()
    db.commit()
    return {"authorized": True, "message": "정상 인증",
            "expires_at": lic.expires_at.isoformat() if lic.expires_at else None}

@app.post("/verify")
def verify_device(req: DeviceVerify, db: Session = Depends(get_db)):
    """단순 HWID 기반 검증 (클라이언트 앱 전용)"""
    dev = db.query(Device).filter(Device.hwid == req.hwid).first()
    if not dev:
        return {"authorized": False, "message": "등록되지 않은 기기입니다.", "status": "unregistered"}
    if dev.status == "approved":
        return {"authorized": True, "message": "인증 성공", "status": "approved"}
    elif dev.status == "pending":
        return {"authorized": False, "message": "승인 대기 중입니다.", "status": "pending"}
    else:
        return {"authorized": False, "message": "차단된 기기입니다.", "status": "blocked"}

@app.post("/request_approval")
def request_approval(req: ApprovalRequest, db: Session = Depends(get_db)):
    """클라이언트 앱에서 관리자에게 승인 요청"""
    dev = db.query(Device).filter(Device.hwid == req.hwid).first()
    if not dev:
        dev = Device(hwid=req.hwid, name=req.name, status="pending")
        db.add(dev)
    else:
        dev.name = req.name
        if dev.status == "blocked":
            return {"success": False, "message": "차단된 기기는 재요청할 수 없습니다."}
        dev.status = "pending"
    db.commit()
    return {"success": True, "message": "승인 요청이 완료되었습니다."}

# ──────────────────────────────────────────────────────────────────────────
# 관리자 엔드포인트 (x-admin-token 헤더 필요)
# ──────────────────────────────────────────────────────────────────────────
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # 헷갈리는 0/O/1/I 제외


def _gen_code() -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(16))
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))  # XXXX-XXXX-XXXX-XXXX


class IssueRequest(BaseModel):
    count: int = 1
    memo: str = ""
    valid_days: int = 0          # 0 = 무기한
    max_activations: int = 1


@app.post("/admin/issue")
def admin_issue(req: IssueRequest, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    out = []
    expires_at = None
    if req.valid_days and req.valid_days > 0:
        expires_at = datetime.utcnow() + timedelta(days=req.valid_days)
    for _i in range(max(1, req.count)):
        code = _gen_code()
        while db.query(License).filter(License.code == code).first():
            code = _gen_code()
        lic = License(code=code, memo=req.memo, max_activations=req.max_activations,
                      expires_at=expires_at)
        db.add(lic)
        out.append(code)
    db.commit()
    return {"issued": out, "count": len(out)}


class CodeRequest(BaseModel):
    code: str


@app.post("/admin/revoke")
def admin_revoke(req: CodeRequest, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.code == req.code.strip().upper()).first()
    if not lic:
        raise HTTPException(status_code=404, detail="없는 코드")
    lic.is_active = False
    db.commit()
    return {"success": True, "message": "차단됨"}


@app.post("/admin/unrevoke")
def admin_unrevoke(req: CodeRequest, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.code == req.code.strip().upper()).first()
    if not lic:
        raise HTTPException(status_code=404, detail="없는 코드")
    lic.is_active = True
    db.commit()
    return {"success": True, "message": "차단 해제됨"}


@app.post("/admin/reset")
def admin_reset(req: CodeRequest, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    """PC 이전: HWID 바인딩을 풀어 다른 PC 에서 재활성화 가능하게 함."""
    lic = db.query(License).filter(License.code == req.code.strip().upper()).first()
    if not lic:
        raise HTTPException(status_code=404, detail="없는 코드")
    lic.hwid = None
    lic.machine_name = None
    lic.activated_at = None
    db.commit()
    return {"success": True, "message": "PC 바인딩이 해제되었습니다. 새 PC 에서 다시 인증하세요."}


@app.get("/admin/list")
def admin_list(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    return [_public(l) for l in db.query(License).order_by(License.created_at.desc()).all()]

class DeviceApproveRequest(BaseModel):
    hwid: str
    status: str # approved, blocked, pending

@app.post("/admin/device/status")
def admin_device_status(req: DeviceApproveRequest, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    dev = db.query(Device).filter(Device.hwid == req.hwid).first()
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    dev.status = req.status
    db.commit()
    return {"success": True, "message": f"기기 상태가 {req.status}로 변경되었습니다."}

@app.get("/admin/devices")
def admin_devices_list(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    out = []
    for d in db.query(Device).order_by(Device.created_at.desc()).all():
        out.append({
            "hwid": d.hwid,
            "name": d.name,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None
        })
    return out

@app.get("/health")
def health():
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# 계정 시스템 (회원가입 → 5일 무료 체험 → 로그인 검증)
# ══════════════════════════════════════════════════════════════════════════
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return "pbkdf2$200000$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iters, salt_b64, dk_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def make_token(email: str, ttl_hours: int = 24 * 7) -> str:
    """HMAC 서명된 stateless 토큰 (추가 라이브러리 없이)."""
    payload = {"sub": email, "exp": int((datetime.utcnow() + timedelta(hours=ttl_hours)).timestamp())}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def parse_token(token: str) -> str | None:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, expected):
            return None
        pad = "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body + pad))
        if payload.get("exp", 0) < datetime.utcnow().timestamp():
            return None
        return payload.get("sub")
    except Exception:
        return None


def current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:]
    email = parse_token(token) if token else None
    if not email:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="존재하지 않는 계정입니다.")
    return user


def account_status(user: User) -> dict:
    """이 계정이 지금 사용 가능한지 + 남은 기간."""
    now = datetime.utcnow()
    if not user.is_active or user.plan == "blocked":
        return {"allowed": False, "plan": "blocked", "message": "차단된 계정입니다.", "days_left": 0}

    if user.plan == "paid":
        if user.paid_expires_at and user.paid_expires_at < now:
            return {"allowed": False, "plan": "paid", "message": "유료 이용 기간이 만료되었습니다.", "days_left": 0}
        days_left = (user.paid_expires_at - now).days if user.paid_expires_at else 9999
        return {"allowed": True, "plan": "paid", "message": "정상 이용 중",
                "days_left": days_left, "expires_at": user.paid_expires_at.isoformat() if user.paid_expires_at else None}

    # trial
    exp = user.trial_expires_at
    if exp and exp >= now:
        secs = (exp - now).total_seconds()
        days_left = int(secs // 86400) + (1 if secs % 86400 else 0)
        return {"allowed": True, "plan": "trial", "message": f"무료 체험 중 (약 {days_left}일 남음)",
                "days_left": days_left, "expires_at": exp.isoformat()}
    return {"allowed": False, "plan": "trial",
            "message": "무료 체험 기간이 끝났습니다. 정식 이용을 원하시면 결제/문의해 주세요.",
            "days_left": 0, "expires_at": exp.isoformat() if exp else None}


class RegisterUser(BaseModel):
    email: str
    password: str


class LoginUser(BaseModel):
    email: str
    password: str


def _norm_email(e: str) -> str:
    return (e or "").strip().lower()


@app.post("/register")
def register(req: RegisterUser, db: Session = Depends(get_db)):
    email = _norm_email(req.email)
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="올바른 이메일을 입력하세요.")
    if len(req.password or "") < 6:
        raise HTTPException(status_code=400, detail="비밀번호는 6자 이상이어야 합니다.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다. 로그인해 주세요.")

    now = datetime.utcnow()
    user = User(
        email=email,
        password_hash=hash_password(req.password),
        plan="trial",
        trial_expires_at=now + timedelta(days=TRIAL_DAYS),
        last_login=now,
    )
    db.add(user)
    db.commit()
    return {
        "token": make_token(email),
        "status": account_status(user),
        "message": f"가입 완료! {TRIAL_DAYS}일 무료 체험이 시작되었습니다.",
    }


@app.post("/login")
def login(req: LoginUser, db: Session = Depends(get_db)):
    email = _norm_email(req.email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    user.last_login = datetime.utcnow()
    db.commit()
    return {"token": make_token(email), "status": account_status(user)}


@app.get("/me")
def me(user: User = Depends(current_user)):
    """프로그램/웹이 실행 시 호출 — 현재 사용 가능 여부와 남은 기간."""
    return {"email": user.email, "status": account_status(user)}


# ── 계정 관리자 엔드포인트 ────────────────────────────────────────────────
class UpgradeRequest(BaseModel):
    email: str
    days: int = 365          # 유료 부여 일수(0=무기한)


@app.post("/admin/upgrade")
def admin_upgrade(req: UpgradeRequest, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == _norm_email(req.email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="없는 계정")
    user.plan = "paid"
    user.is_active = True
    user.paid_expires_at = (datetime.utcnow() + timedelta(days=req.days)) if req.days > 0 else None
    db.commit()
    return {"success": True, "status": account_status(user)}


class EmailRequest(BaseModel):
    email: str


@app.post("/admin/block_user")
def admin_block_user(req: EmailRequest, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == _norm_email(req.email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="없는 계정")
    user.plan = "blocked"
    user.is_active = False
    db.commit()
    return {"success": True, "message": "차단됨"}


@app.post("/admin/extend_trial")
def admin_extend_trial(req: UpgradeRequest, _: bool = Depends(require_admin), db: Session = Depends(get_db)):
    """체험 기간 연장(테스트/영업용)."""
    user = db.query(User).filter(User.email == _norm_email(req.email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="없는 계정")
    base = max(user.trial_expires_at or datetime.utcnow(), datetime.utcnow())
    user.trial_expires_at = base + timedelta(days=req.days or TRIAL_DAYS)
    user.plan = "trial"
    user.is_active = True
    db.commit()
    return {"success": True, "status": account_status(user)}


@app.get("/admin/users")
def admin_users(_: bool = Depends(require_admin), db: Session = Depends(get_db)):
    out = []
    for u in db.query(User).order_by(User.created_at.desc()).all():
        st = account_status(u)
        out.append({"email": u.email, "plan": u.plan, "allowed": st["allowed"],
                    "days_left": st["days_left"],
                    "trial_expires_at": u.trial_expires_at.isoformat() if u.trial_expires_at else None,
                    "paid_expires_at": u.paid_expires_at.isoformat() if u.paid_expires_at else None,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_login": u.last_login.isoformat() if u.last_login else None})
    return out


# ── 웹 가입/로그인 페이지 ─────────────────────────────────────────────────
_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__BRAND__ 가입 / 로그인</title>
<style>
 *{box-sizing:border-box;font-family:'맑은 고딕',system-ui,sans-serif}
 body{margin:0;background:#0f172a;color:#e2e8f0;display:flex;min-height:100vh;align-items:center;justify-content:center}
 .card{background:#1e293b;padding:36px 32px;border-radius:16px;width:360px;box-shadow:0 20px 60px rgba(0,0,0,.4)}
 h1{font-size:22px;margin:0 0 4px}.sub{color:#94a3b8;font-size:13px;margin-bottom:22px}
 label{font-size:13px;color:#cbd5e1;display:block;margin:14px 0 6px}
 input{width:100%;padding:12px;border-radius:9px;border:1px solid #334155;background:#0f172a;color:#fff;font-size:14px}
 button{width:100%;margin-top:20px;padding:13px;border:0;border-radius:9px;background:#3b82f6;color:#fff;font-size:15px;font-weight:600;cursor:pointer}
 button:hover{background:#2563eb}.tabs{display:flex;gap:8px;margin-bottom:18px}
 .tabs a{flex:1;text-align:center;padding:9px;border-radius:8px;background:#0f172a;color:#94a3b8;cursor:pointer;font-size:14px;text-decoration:none}
 .tabs a.on{background:#3b82f6;color:#fff}
 .msg{margin-top:16px;font-size:13px;padding:11px;border-radius:8px;display:none}
 .ok{background:#064e3b;color:#6ee7b7}.err{background:#4c1d1d;color:#fca5a5}
 .note{margin-top:18px;font-size:12px;color:#64748b;text-align:center}
</style></head><body>

<div class="card" id="authCard">
 <h1>__BRAND__</h1>
 <div class="sub">회원가입하면 __TRIAL__일 무료 체험이 시작됩니다.</div>
 <div class="tabs"><a id="t-signup" class="on" onclick="mode('signup')">회원가입</a><a id="t-login" onclick="mode('login')">로그인</a></div>
 <label>이메일</label><input id="email" type="email" placeholder="you@example.com">
 <label>비밀번호</label><input id="pw" type="password" placeholder="6자 이상" onkeydown="if(event.key==='Enter')submit()">
 <button id="go" onclick="submit()">무료로 시작하기</button>
 <div id="msg" class="msg"></div>
 <div class="note">PC·위치 제한 없이 어디서든 같은 계정으로 사용</div>
</div>

<script>
const APP_URL="__APP_URL__";
let M='signup';
function mode(m){M=m;
 document.getElementById('t-signup').className=m==='signup'?'on':'';
 document.getElementById('t-login').className=m==='login'?'on':'';
 document.getElementById('go').textContent=m==='signup'?'무료로 시작하기':'로그인';
 hide();}
function show(t,ok){const e=document.getElementById('msg');e.textContent=t;e.className='msg '+(ok?'ok':'err');e.style.display='block';}
function hide(){document.getElementById('msg').style.display='none';}
function goApp(){location.href=APP_URL;}

async function submit(){
 hide();const email=document.getElementById('email').value,pw=document.getElementById('pw').value;
 const url=M==='signup'?'/register':'/login';
 try{
  const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,password:pw})});
  const d=await r.json();
  if(!r.ok){show(d.detail||'오류',false);return;}
  localStorage.setItem('mbam_token',d.token);
  const s=d.status||{};
  if(s.allowed===false){show(s.message||'이용 기간이 만료되었습니다.',false);return;}
  goApp();                       // ★ 로그인 성공 → 사이트로 이동
 }catch(e){show('서버에 연결할 수 없습니다.',false);}
}

// 이미 로그인돼 있으면 바로 사이트로 이동
(async function(){
 const t=localStorage.getItem('mbam_token');
 if(!t)return;
 try{
  const r=await fetch('/me',{headers:{'Authorization':'Bearer '+t}});
  if(r.ok){const d=await r.json();if(d.status&&d.status.allowed){goApp();}}
  else localStorage.removeItem('mbam_token');
 }catch(e){}
})();
</script></body></html>"""


# ── 로그인 후 이동하는 사이트(데모 /app). 실제 분석 웹으로 교체 가능 ───────
_APP = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__BRAND__</title>
<style>
 *{box-sizing:border-box;font-family:'맑은 고딕',system-ui,sans-serif}
 body{margin:0;background:#0b1220;color:#e2e8f0}
 .top{display:flex;align-items:center;justify-content:space-between;padding:16px 24px;background:#111a2e;border-bottom:1px solid #1e293b}
 .brand{font-size:18px;font-weight:700}
 .right{display:flex;align-items:center;gap:14px;font-size:13px;color:#94a3b8}
 .badge{padding:4px 10px;border-radius:999px;font-size:12px;font-weight:600;background:#1e3a8a;color:#bfdbfe}
 .badge.paid{background:#064e3b;color:#6ee7b7}
 button{border:0;border-radius:8px;background:#334155;color:#e2e8f0;padding:7px 12px;cursor:pointer;font-size:13px}
 button:hover{background:#475569}
 .wrap{max-width:1000px;margin:32px auto;padding:0 24px}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;margin-top:20px}
 .tile{background:#1e293b;border:1px solid #243049;border-radius:14px;padding:22px;cursor:pointer}
 .tile:hover{border-color:#3b82f6}.tile h3{margin:0 0 6px;font-size:16px}.tile p{margin:0;color:#94a3b8;font-size:13px}
 h2{font-size:22px}.muted{color:#94a3b8;font-size:14px}
</style></head><body>
 <div class="top">
   <div class="brand">__BRAND__</div>
   <div class="right">
     <span id="email"></span><span class="badge" id="badge"></span>
     <button onclick="logout()">로그아웃</button>
   </div>
 </div>
 <div class="wrap">
   <h2>안녕하세요 👋</h2>
   <div class="muted" id="welcome"></div>
   <div class="grid">
     <div class="tile"><h3>🔍 SEO 분석</h3><p>키워드·상위노출 분석</p></div>
     <div class="tile"><h3>📍 플레이스 진단</h3><p>플레이스 순위·점수</p></div>
     <div class="tile"><h3>☕ 카페글 분석</h3><p>작성자·카페 권위</p></div>
     <div class="tile"><h3>🛒 쇼핑/쿠팡 추적</h3><p>상품 순위 변화</p></div>
   </div>
   <p class="muted" style="margin-top:28px">※ 위 메뉴는 자리표시(데모)입니다. 실제 분석 화면을 여기에 연결합니다.</p>
 </div>
<script>
function logout(){localStorage.removeItem('mbam_token');location.href='/';}
(async function(){
 const t=localStorage.getItem('mbam_token');
 if(!t){location.href='/';return;}
 try{
  const r=await fetch('/me',{headers:{'Authorization':'Bearer '+t}});
  if(!r.ok){localStorage.removeItem('mbam_token');location.href='/';return;}
  const d=await r.json(); const s=d.status||{};
  if(!s.allowed){alert(s.message||'이용 기간이 만료되었습니다.');localStorage.removeItem('mbam_token');location.href='/';return;}
  document.getElementById('email').textContent=d.email||'';
  const b=document.getElementById('badge');
  b.textContent=(s.plan==='paid'?'정식 이용':'무료 체험');b.className='badge '+(s.plan==='paid'?'paid':'');
  document.getElementById('welcome').textContent=(s.message||'')+(s.days_left<9999?'':'');
 }catch(e){location.href='/';}
})();
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return (_PAGE.replace("__TRIAL__", str(TRIAL_DAYS))
                 .replace("__BRAND__", BRAND)
                 .replace("__APP_URL__", APP_URL))


@app.get("/app", response_class=HTMLResponse)
def app_page():
    return _APP.replace("__BRAND__", BRAND)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8005")))
