"""
통합 네이버 계정 관리 라우터 (/api/accounts).

설정 > 계정 관리 화면과 블로그/카페 포스팅 계정 추가가 공유하는 단일 저장소.
- 저장소: NaverAccount 테이블 (사용자별)
- 인증여부: profiles/{naver_id}/.registered 디바이스 인증 마커
- 등록일: created_at
"""
import os
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db, NaverAccount
from ..auth import get_current_user
from mbam_nextgen.infrastructure.session import (
    is_registered, get_profile_dir, mark_registered, clear_stale_locks,
)

router = APIRouter(prefix="/api/accounts", tags=["Account Management"])


def _user_id(current_user: dict) -> str:
    return current_user.get("sub")


class AccountUpsert(BaseModel):
    naver_id: str
    naver_pw: Optional[str] = None
    blog_addr: Optional[str] = None


class AccountEdit(BaseModel):
    naver_pw: Optional[str] = None
    blog_addr: Optional[str] = None
    status: Optional[str] = None


# ── 기기 인증 상태를 '클라우드에서 보이게' 저장 ──────────────────────────────
# 문제: 기기 인증은 사용자 PC(에이전트)에서 실행돼 .registered 마커가 그 PC에만 생김.
# 클라우드 백엔드는 자기 파일시스템만 봐서 항상 '미인증'으로 표시됐다.
# 해결: 인증 완료를 app_settings(DB, KV)에 기록하고, 목록/상태 조회 시 그 값도 함께 본다.
def _reg_key(uid: str, naver_id: str) -> str:
    return f"device_reg:{uid}:{naver_id}"


def _kv_set_registered(uid: str, naver_id: str):
    try:
        from .settings import db_set_settings
        db_set_settings({_reg_key(uid, naver_id): "1"})
    except Exception as e:
        print(f"[account] 인증상태 저장 실패: {e}")


def _kv_is_registered(uid: str, naver_id: str) -> bool:
    try:
        from .settings import db_get_settings
        k = _reg_key(uid, naver_id)
        return db_get_settings([k]).get(k) == "1"
    except Exception:
        return False


def _persist_register_account(db, user_id, payload, result):
    """[방법 B] 에이전트가 기기 인증을 마치면 클라우드 DB에 '인증 완료'를 기록(cloud 영속화 훅)."""
    if result and result.get("success"):
        nid = (payload or {}).get("naver_id")
        if nid:
            _kv_set_registered(user_id, nid)


try:
    from ..import jobs as _jobs_mod  # noqa
except Exception:
    _jobs_mod = None
try:
    from mbam_nextgen.backend import jobs as _jobs_mod
    _jobs_mod.register_persister("register_account", _persist_register_account)
except Exception as _e:
    print(f"[account] register_account persister 등록 실패: {_e}")


def _serialize(acc: NaverAccount, uid: str = None) -> dict:
    return {
        "id": acc.id,
        "naver_id": acc.naver_id,
        "blog_addr": acc.blog_addr or "",
        "status": acc.status or "active",
        "has_pw": bool(acc.naver_pw),
        # 로컬 파일 마커(설치형) 또는 클라우드 KV 기록(방법 B) 둘 중 하나면 인증 완료
        "registered": is_registered(acc.naver_id) or _kv_is_registered(uid or acc.user_id, acc.naver_id),
        "created_at": acc.created_at.isoformat() if acc.created_at else None,
    }


class AIKeysUpsert(BaseModel):
    claude_key: Optional[str] = None
    gemini_key: Optional[str] = None
    openai_key: Optional[str] = None


def _mask(v: Optional[str]) -> str:
    if not v:
        return ""
    return ("•" * max(0, len(v) - 4)) + v[-4:] if len(v) > 4 else "••••"


@router.get("/ai-keys", summary="내 AI 키(BYOK) 조회 — 마스킹")
async def get_my_ai_keys(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from ..models import UserAIKey
    uid = _user_id(current_user)
    rec = db.query(UserAIKey).filter(UserAIKey.user_id == uid).first()
    if not rec:
        return {"claude": "", "gemini": "", "openai": "", "has": {"claude": False, "gemini": False, "openai": False}}
    return {
        "claude": _mask(rec.claude_key), "gemini": _mask(rec.gemini_key), "openai": _mask(rec.openai_key),
        "has": {"claude": bool(rec.claude_key), "gemini": bool(rec.gemini_key), "openai": bool(rec.openai_key)},
    }


@router.post("/ai-keys", summary="내 AI 키(BYOK) 저장 — 설치형 고객용")
async def save_my_ai_keys(req: AIKeysUpsert, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    from ..models import UserAIKey
    uid = _user_id(current_user)
    rec = db.query(UserAIKey).filter(UserAIKey.user_id == uid).first()
    if not rec:
        rec = UserAIKey(user_id=uid)
        db.add(rec)
    # 전달된 값만 갱신(빈 문자열로 덮어쓰지 않음). 명시적 삭제는 "-" 로.
    if req.claude_key is not None and req.claude_key.strip():
        rec.claude_key = None if req.claude_key.strip() == "-" else req.claude_key.strip()
    if req.gemini_key is not None and req.gemini_key.strip():
        rec.gemini_key = None if req.gemini_key.strip() == "-" else req.gemini_key.strip()
    if req.openai_key is not None and req.openai_key.strip():
        rec.openai_key = None if req.openai_key.strip() == "-" else req.openai_key.strip()
    db.commit()
    return {"success": True, "message": "AI 키가 저장되었습니다. 이제 글 생성이 본인 키로 청구됩니다."}


@router.get("", summary="저장된 네이버 계정 목록(등록일·인증여부 포함)")
async def list_accounts(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _user_id(current_user)
    accounts = db.query(NaverAccount).filter(NaverAccount.user_id == uid).order_by(NaverAccount.created_at.desc()).all()
    try:
        import logging
        _all = db.query(NaverAccount).count()
        logging.getLogger("uvicorn.error").error(f"[account_router] list_accounts uid={uid!r} → {len(accounts)}개 (DB 전체 {_all}개)")
    except Exception:
        pass
    return {"accounts": [_serialize(a, uid) for a in accounts]}


@router.post("", summary="계정 추가 또는 갱신(upsert) — 포스팅 화면의 '계정 추가'도 여기로 저장")
async def upsert_account(req: AccountUpsert, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _user_id(current_user)
    naver_id = (req.naver_id or "").strip()
    if not naver_id:
        raise HTTPException(status_code=400, detail="네이버 아이디를 입력하세요.")

    acc = db.query(NaverAccount).filter(NaverAccount.user_id == uid, NaverAccount.naver_id == naver_id).first()
    created = False
    if not acc:
        acc = NaverAccount(user_id=uid, naver_id=naver_id)
        db.add(acc)
        created = True
    # 전달된 값만 갱신(빈 값으로 덮어쓰지 않음)
    if req.naver_pw:
        acc.naver_pw = req.naver_pw  # TODO: 운영 시 암호화
    if req.blog_addr is not None and req.blog_addr.strip():
        acc.blog_addr = req.blog_addr.strip()
    db.commit()
    db.refresh(acc)
    return {"message": "계정이 추가되었습니다." if created else "계정이 갱신되었습니다.", "created": created, "account": _serialize(acc)}


@router.put("/{account_id}", summary="계정 수정(블로그 주소/비밀번호/상태)")
async def edit_account(account_id: str, req: AccountEdit, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _user_id(current_user)
    acc = db.query(NaverAccount).filter(NaverAccount.id == account_id, NaverAccount.user_id == uid).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    if req.naver_pw:
        acc.naver_pw = req.naver_pw
    if req.blog_addr is not None:
        acc.blog_addr = req.blog_addr.strip() or None
    if req.status:
        acc.status = req.status
    db.commit()
    db.refresh(acc)
    return {"message": "수정되었습니다.", "account": _serialize(acc)}


@router.delete("/{account_id}", summary="계정 삭제(디바이스 인증 프로필도 함께 제거)")
async def delete_account(account_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _user_id(current_user)
    acc = db.query(NaverAccount).filter(NaverAccount.id == account_id, NaverAccount.user_id == uid).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    naver_id = acc.naver_id
    db.delete(acc)
    db.commit()

    # 디바이스 인증 프로필 디렉터리도 제거 (best-effort)
    removed_profile = False
    try:
        import shutil
        pdir = get_profile_dir(naver_id)
        if pdir and os.path.isdir(pdir):
            shutil.rmtree(pdir, ignore_errors=True)
            removed_profile = True
    except Exception:
        pass
    return {"message": "계정이 삭제되었습니다.", "removed_profile": removed_profile}


# ──────────────────────────────────────────────────────────────────────────
# 기기 인증 (디바이스 등록) — 영구 프로필로 1회 수동 로그인하여 네이버 신뢰 기기로 등록
#   profiles/{naver_id} 프로필에 브라우저(headless=False)를 띄워 저장된 ID/PW를 자동입력하고,
#   캡챠/2단계 인증은 사용자가 창에서 직접 완료. 로그인 성공이 감지되면 .registered 마커 생성.
# 진행 상태는 naver_id 기준 메모리 스토어에 보관(중복 실행 방지 + 프론트 폴링).
# ──────────────────────────────────────────────────────────────────────────
device_auth_tasks: dict = {}  # naver_id -> {"status": running|completed|failed, "message": str, "logs": [str]}


async def _run_device_auth(naver_id: str, naver_pw: Optional[str], uid: Optional[str] = None):
    state = device_auth_tasks[naver_id]

    def log(msg: str):
        state["logs"].append(msg)
        print(f"[device-auth:{naver_id}] {msg}")

    context = None
    try:
        from playwright.async_api import async_playwright
        from mbam_nextgen.infrastructure.naver_auth import NaverAuthenticator
        from mbam_nextgen.infrastructure.session import SessionManager

        sm = SessionManager()
        profile_dir = get_profile_dir(naver_id)
        clear_stale_locks(naver_id)  # 이전 비정상 종료로 남은 프로필 잠금/좀비 크롬 정리

        log("브라우저를 실행합니다. 잠시만 기다려 주세요...")
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                profile_dir,
                headless=False,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="ko-KR",
                timezone_id="Asia/Seoul",
            )
            page = context.pages[0] if context.pages else await context.new_page()
            page.on("dialog", lambda d: asyncio.create_task(d.accept()))

            if naver_pw:
                log("저장된 ID/PW를 자동 입력합니다. 캡챠/2단계 인증이 뜨면 창에서 직접 완료해 주세요.")
            else:
                log("저장된 비밀번호가 없습니다. 열린 창에서 직접 로그인을 완료해 주세요. (최대 5분 대기)")

            authenticator = NaverAuthenticator()
            ok = await authenticator.login_with_bypass(page, naver_id, naver_pw or "", manual_wait_secs=300)

            if ok:
                mark_registered(naver_id)
                if uid:
                    _kv_set_registered(uid, naver_id)  # 클라우드에서도 보이도록 DB 기록
                try:
                    await sm.save_session(context, naver_id)
                except Exception:
                    pass
                state["status"] = "completed"
                state["message"] = "기기 인증이 완료되었습니다. 이제 자동 로그인됩니다."
                log("✅ 로그인 성공 — 기기 인증 완료. 잠시 후 창이 닫힙니다.")
                await asyncio.sleep(3)
            else:
                state["status"] = "failed"
                state["message"] = "로그인이 확인되지 않았습니다. 비밀번호/2단계 인증을 확인 후 다시 시도해 주세요."
                log("❌ 제한 시간 내 로그인이 확인되지 않았습니다.")
    except Exception as e:
        state["status"] = "failed"
        state["message"] = f"기기 인증 중 오류: {e}"
        log(f"❌ 오류: {e}")
    finally:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass


@router.post("/{account_id}/register-device", summary="기기 인증 시작(브라우저 1회 수동 로그인)")
async def register_device(account_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _user_id(current_user)
    acc = db.query(NaverAccount).filter(NaverAccount.id == account_id, NaverAccount.user_id == uid).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")

    naver_id = acc.naver_id
    # [방법 B] 클라우드는 브라우저를 못 여므로 로컬 에이전트에 위임(register_account 잡).
    from mbam_nextgen.backend import jobs as jobsvc
    if jobsvc.is_cloud_mode():
        job_id = jobsvc.enqueue_job(db, uid, "register_account", {"naver_id": naver_id, "naver_pw": acc.naver_pw})
        device_auth_tasks[naver_id] = {"status": "running", "message": "내 PC에서 브라우저가 열립니다. 로그인 + 2단계 인증을 완료해 주세요. (로컬 에이전트 실행 필요)", "logs": [], "job_id": job_id}
        return {"success": True, "mode": "agent", "job_id": job_id,
                "message": "내 PC에서 브라우저가 열립니다. 로그인 + 2단계 인증을 완료해 주세요.", "naver_id": naver_id}

    existing = device_auth_tasks.get(naver_id)
    if existing and existing.get("status") == "running":
        return {"success": True, "message": "이미 기기 인증이 진행 중입니다. 열린 브라우저 창에서 로그인을 완료해 주세요.", "naver_id": naver_id}

    device_auth_tasks[naver_id] = {"status": "running", "message": "기기 인증을 시작합니다...", "logs": []}
    asyncio.create_task(_run_device_auth(naver_id, acc.naver_pw, uid))
    return {"success": True, "message": "기기 인증을 시작했습니다. 잠시 후 뜨는 브라우저 창에서 로그인을 완료해 주세요.", "naver_id": naver_id}


@router.get("/{account_id}/register-device/status", summary="기기 인증 진행 상태")
async def register_device_status(account_id: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    uid = _user_id(current_user)
    acc = db.query(NaverAccount).filter(NaverAccount.id == account_id, NaverAccount.user_id == uid).first()
    if not acc:
        raise HTTPException(status_code=404, detail="계정을 찾을 수 없습니다.")
    registered = is_registered(acc.naver_id) or _kv_is_registered(uid, acc.naver_id)
    state = device_auth_tasks.get(acc.naver_id)
    # 클라우드: 에이전트가 인증을 마치면 persister가 KV에 기록 → 그걸로 완료 판정
    if registered:
        return {"status": "completed", "message": "기기 인증이 완료되었습니다. 이제 자동 로그인됩니다.",
                "logs": (state or {}).get("logs", []), "registered": True}
    if not state:
        return {"status": "idle", "message": "", "logs": [], "registered": registered}
    return {**state, "registered": registered}
